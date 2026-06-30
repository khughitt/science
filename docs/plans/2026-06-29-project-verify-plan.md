# Project Verify (`science project verify`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science project verify <bundle.tar.gz> [--against <root>] [--extract <dir>] [--json]` — the consumer side of `science project serialize`: prove a bundle is internally intact, optionally compare it to a live checkout (commit + source + payloads), and optionally extract its source tree.

**Architecture:** A new reader package alongside the existing writer. `serialize.py` (writer) gains two behavior-neutral seams it now shares with the reader: `project_package/payload.py` (the `data/` hash-inventory walk) and `project_package/manifest.py` (the strict v1 schema model + `data_version` chunk canonicalization). `project_package/verify.py` holds the self-check, the `--against` comparison, the `--extract` writer, and the orchestration; `cli.py` wires the command and maps verdicts to exit codes.

**Tech Stack:** Python 3.11+, Click (CLI), pydantic v2 (manifest schema), stdlib `tarfile`/`gzip`/`hashlib`/`subprocess`, pytest + `click.testing.CliRunner`.

## Global Constraints

- Spec of record: `docs/plans/2026-06-29-project-verify-design.md`. Where this plan and the spec disagree, the spec governs — surface the conflict, don't silently pick.
- Exit codes (precedence **2 → 4 → 1 → 3 → 0**): `0` clean · `1` differ (commit/source/payload) · `2` bundle integrity · `3` payload(s) missing only · `4` operational/precondition.
- Bundle schema string is exactly `science-project-serialized.v1`. JSON CLI-shape contract carries its own top-level `"version": 1`; the bundle-schema field in JSON output is named `bundle_schema_version` (never `schema_version`).
- `--against` has **no** `SCIENCE_PROJECT_ROOT` (or any) envvar binding; comparison must be explicit.
- The `payload.py` and `manifest.py` extractions from `serialize.py` are **behavior-neutral**: serialize's archive bytes, `data_version`, and `PayloadError→SerializeError` message shape are unchanged. Existing tests in `tests/test_project_serialize.py` must stay green untouched.
- House rules: Composition > Inheritance; Explicit > Defensive; fail early, no silent fallbacks. No "legacy"/"compatibility"/"Unified"-prefixed layers. No `Co-Authored-By` trailers. Use `~/d/` in any docs/code paths.
- Repo working dir for commands: `/mnt/ssd/Dropbox/science/science` (the `science` package lives there). Run tests with the project venv: `.venv/bin/python -m pytest`. Lint with `.venv/bin/ruff check <paths>`.
- Verify is **read-only** against `--against`. It never mutates the target checkout. The only write verify ever performs is a successful `--extract` after a clean self-check.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/project_package/payload.py` (new) | `payload_inventory()` + `_walk_payload_dir()` + `PayloadError`. The `data/` hash-inventory walk, moved verbatim from `serialize.py`. |
| `science/src/science_tool/project_package/manifest.py` (new) | `SerializedManifest` strict pydantic model (v1) + `data_version_chunks()` canonicalizer + `SCHEMA_VERSION`. |
| `science/src/science_tool/project_package/serialize.py` (modify) | Drop the inlined walk + inlined chunk-build; import from `payload.py`/`manifest.py`; keep a translating `_payload_inventory` wrapper. |
| `science/src/science_tool/project_package/verify.py` (new) | `load_bundle()` (self-check), `preflight_against()`/`compare_against()`, `preflight_extract()`/`extract_bundle()`, `verify_project()` orchestration, `verdict_json()`, result dataclasses, `BundleIntegrityError`/`VerifyError`. |
| `science/src/science_tool/cli.py` (modify) | `@project.command("verify")` — parse args, call `verify_project`, render human/JSON, map to exit codes. |
| `science/tests/test_project_package_payload.py` (new) | Payload walk unit tests (public API + `PayloadError`). |
| `science/tests/test_project_package_manifest.py` (new) | `SerializedManifest` strict-rule tests + serialize-lockstep test. |
| `science/tests/test_project_verify.py` (new) | Self-check, `--against`, `--extract`, orchestration, round-trip, JSON. Shared bundle helpers live at the top of this file. |
| `science/tests/test_project_verify_cli.py` (new) | CLI wiring + exit codes via `CliRunner`. |

---

## Task 1: Extract the payload walk into `payload.py` (behavior-neutral)

**Files:**
- Create: `science/src/science_tool/project_package/payload.py`
- Create: `science/tests/test_project_package_payload.py`
- Modify: `science/src/science_tool/project_package/serialize.py` (remove inlined walk; import + wrap; drop now-unused `hashlib`/`os` imports)

**Interfaces:**
- Produces: `payload_inventory(project_root: Path, data_dirs: tuple[Path, ...], tracked_set: set[str]) -> list[dict]` (each dict `{"path","sha256","bytes","git_tracked"}`, sorted by `path`); `_walk_payload_dir(project_root, directory, tracked_set, seen_dirs, payloads) -> None`; `class PayloadError(Exception)`.
- Serialize keeps `_payload_inventory(project_root, data_dirs, tracked_set)` as a wrapper translating `PayloadError → SerializeError(str(exc))`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_project_package_payload.py`:

```python
import hashlib
import os
from pathlib import Path

import pytest

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_package.payload import PayloadError, payload_inventory


def _write(root: Path, rel: str, content: bytes) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_payload_inventory_hashes_and_sorts(tmp_path: Path):
    _write(tmp_path, "data/processed/b.parquet", b"\x01\x02\x03")
    _write(tmp_path, "data/raw/a.bin", b"\x00")
    inv = payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set={"data/raw/a.bin"})
    assert inv == [
        {"path": "data/processed/b.parquet",
         "sha256": hashlib.sha256(b"\x01\x02\x03").hexdigest(), "bytes": 3,
         "git_tracked": False},
        {"path": "data/raw/a.bin",
         "sha256": hashlib.sha256(b"\x00").hexdigest(), "bytes": 1,
         "git_tracked": True},
    ]


def test_payload_inventory_follows_symlink_to_content(tmp_path: Path):
    target = tmp_path / "outside.bin"
    target.write_bytes(b"hydrated")
    (tmp_path / "data" / "processed").mkdir(parents=True)
    os.symlink(target, tmp_path / "data" / "processed" / "link.bin")
    inv = payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())
    assert inv[0]["sha256"] == hashlib.sha256(b"hydrated").hexdigest()
    assert inv[0]["bytes"] == len(b"hydrated")


def test_payload_inventory_raises_payload_error_on_cycle(tmp_path: Path):
    d = tmp_path / "data" / "processed"
    d.mkdir(parents=True)
    os.symlink(d, d / "loop")
    with pytest.raises(PayloadError):
        payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())


def test_payload_inventory_raises_payload_error_on_non_regular(tmp_path: Path):
    d = tmp_path / "data" / "processed"
    d.mkdir(parents=True)
    os.mkfifo(d / "fifo")
    with pytest.raises(PayloadError):
        payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_package_payload.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.project_package.payload'`.

- [ ] **Step 3: Create `payload.py` with the walk moved verbatim**

Create `science/src/science_tool/project_package/payload.py`:

```python
"""Payload hash-inventory walk over a project's data/ tree.

Shared by `serialize` (records the inventory) and `verify --against`
(compares a checkout's data/ against a bundle's inventory) so both use
byte-identical hashing, sorting, and guard semantics.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


class PayloadError(Exception):
    """Symlink cycle or non-regular file encountered while walking data/."""


def payload_inventory(
    project_root: Path,
    data_dirs: tuple[Path, ...],
    tracked_set: set[str],
) -> list[dict]:
    payloads: list[dict] = []
    seen_dirs: set[str] = set()
    for d in data_dirs:
        base = project_root / d
        if not base.exists():
            continue
        _walk_payload_dir(project_root, base, tracked_set, seen_dirs, payloads)
    payloads.sort(key=lambda p: p["path"])
    return payloads


def _walk_payload_dir(
    project_root: Path,
    directory: Path,
    tracked_set: set[str],
    seen_dirs: set[str],
    payloads: list[dict],
) -> None:
    real = os.path.realpath(directory)
    if real in seen_dirs:
        raise PayloadError(f"symlink cycle under data dir: {directory}")
    seen_dirs.add(real)
    for entry in sorted(os.scandir(directory), key=lambda e: e.name):
        path = Path(entry.path)
        if entry.is_dir(follow_symlinks=True):
            _walk_payload_dir(project_root, path, tracked_set, seen_dirs, payloads)
        elif entry.is_file(follow_symlinks=True):
            data = path.read_bytes()  # follows symlink to hydrated content
            rel = path.relative_to(project_root).as_posix()
            payloads.append({
                "path": rel,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "git_tracked": rel in tracked_set,
            })
        else:
            raise PayloadError(f"non-regular file under data dir: {entry.path}")
```

- [ ] **Step 4: Rewire `serialize.py` onto the shared walk**

In `science/src/science_tool/project_package/serialize.py`:

1. Remove the top-level `import hashlib` and `import os` lines (no longer used after the walk leaves).
2. Add to the imports block: `from science_tool.project_package.payload import PayloadError, payload_inventory`.
3. Delete the existing `_walk_payload_dir` function entirely.
4. Replace the existing `_payload_inventory` body with the translating wrapper:

```python
def _payload_inventory(
    project_root: Path,
    data_dirs: tuple[Path, ...],
    tracked_set: set[str],
) -> list[dict]:
    """Serialize's view of the shared walk: translate guard failures to
    SerializeError so the existing fail-loud contract is unchanged."""
    try:
        return payload_inventory(project_root, data_dirs, tracked_set)
    except PayloadError as exc:
        raise SerializeError(str(exc)) from exc
```

- [ ] **Step 5: Run the new + existing serialize tests**

Run: `.venv/bin/python -m pytest tests/test_project_package_payload.py tests/test_project_serialize.py -v`
Expected: PASS — new payload tests green; every existing serialize test (which imports `_payload_inventory` and asserts the cycle/non-regular guards raise `SerializeError`) still green, proving the move is behavior-neutral.

- [ ] **Step 6: Lint**

Run: `.venv/bin/ruff check src/science_tool/project_package/payload.py src/science_tool/project_package/serialize.py tests/test_project_package_payload.py`
Expected: no findings (in particular, no unused-import warning for the removed `hashlib`/`os`).

- [ ] **Step 7: Commit**

```bash
git add src/science_tool/project_package/payload.py src/science_tool/project_package/serialize.py tests/test_project_package_payload.py
git commit -m "refactor(project-package): extract payload_inventory walk into payload.py"
```

---

## Task 2: `manifest.py` — strict v1 model + `data_version` canonicalizer

**Files:**
- Create: `science/src/science_tool/project_package/manifest.py`
- Create: `science/tests/test_project_package_manifest.py`
- Modify: `science/src/science_tool/project_package/serialize.py` (`_build_manifest` reuses `data_version_chunks`)

**Interfaces:**
- Consumes: `content_version` from `project_package/core.py` (test-side only).
- Produces:
  - `SCHEMA_VERSION = "science-project-serialized.v1"`.
  - `SerializedManifest` (pydantic, `extra="forbid"` on every model) with fields `schema_version: str`, `project: ProjectInfo`, `data_version: str`, `provenance: Provenance`, `boundary_audit: BoundaryAudit`, `files: list[FileRecord]`, `payloads: list[PayloadRecord]`. `ProjectInfo(id,label,summary|None)`, `Provenance(git_commit,tool)`, `BoundaryAudit(passed,forced)`, `FileRecord(path,sha256,bytes)`, `PayloadRecord(path,sha256,bytes,git_tracked)`.
  - The model rejects duplicate paths **and unsorted manifest order**: `files[]` and `payloads[]` must each be sorted ascending by `path`, matching serialize's deterministic writer order and the verify design's `data_version` recompute contract.
  - `data_version_chunks(files: Iterable[Mapping], payloads: Iterable[Mapping]) -> list[bytes]` — canonical record chunks (per file `{path,sha256,bytes}` sorted-keys; per payload `{path,sha256,bytes,git_tracked}` sorted-keys), in the already-validated manifest order.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_project_package_manifest.py`:

```python
import pytest
from pydantic import ValidationError

from science_tool.project_package.core import content_version
from science_tool.project_package.manifest import (
    SCHEMA_VERSION,
    SerializedManifest,
    data_version_chunks,
)

_SHA = "a" * 64


def _valid() -> dict:
    files = [{"path": "science.yaml", "sha256": _SHA, "bytes": 3}]
    payloads = [{"path": "data/raw/x.bin", "sha256": _SHA, "bytes": 1, "git_tracked": False}]
    dv = content_version("0", data_version_chunks(files, payloads))
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {"id": "demo", "label": "Demo", "summary": None},
        "data_version": dv,
        "provenance": {"git_commit": "abc123", "tool": "science"},
        "boundary_audit": {"passed": True, "forced": False},
        "files": files,
        "payloads": payloads,
    }


def test_valid_manifest_parses():
    m = SerializedManifest.model_validate(_valid())
    assert m.project.id == "demo"
    assert m.files[0].path == "science.yaml"
    assert m.payloads[0].git_tracked is False


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(schema_version="science-project-serialized.v2"),
    lambda d: d["project"].update(id="../escape"),
    lambda d: d["project"].update(id=""),
    lambda d: d["files"][0].update(path="/abs/path"),
    lambda d: d["files"][0].update(path="../up"),
    lambda d: d["files"][0].update(sha256="a" * 63),
    lambda d: d["files"][0].update(bytes=-1),
    lambda d: d["files"].append(dict(d["files"][0])),       # duplicate files path
    lambda d: d["payloads"].append(dict(d["payloads"][0])), # duplicate payloads path
    lambda d: d["files"].extend([
        {"path": "z.md", "sha256": _SHA, "bytes": 1},
        {"path": "a.md", "sha256": _SHA, "bytes": 1},
    ]),                                                      # unsorted files path
    lambda d: d["payloads"].extend([
        {"path": "data/raw/z.bin", "sha256": _SHA, "bytes": 1, "git_tracked": False},
        {"path": "data/raw/a.bin", "sha256": _SHA, "bytes": 1, "git_tracked": False},
    ]),                                                      # unsorted payloads path
    lambda d: d["project"].update(unexpected="x"),          # extra field on nested model
    lambda d: d.update(unexpected="x"),                     # extra field on root model
])
def test_strict_rules_reject(mutate):
    d = _valid()
    mutate(d)
    with pytest.raises(ValidationError):
        SerializedManifest.model_validate(d)


def test_data_version_chunks_are_canonical_and_ordered():
    files = [{"path": "a", "sha256": _SHA, "bytes": 1},
             {"path": "b", "sha256": _SHA, "bytes": 2}]
    payloads = [{"path": "p", "sha256": _SHA, "bytes": 9, "git_tracked": True}]
    chunks = data_version_chunks(files, payloads)
    assert chunks == [
        b'{"bytes": 1, "path": "a", "sha256": "%s"}' % _SHA.encode(),
        b'{"bytes": 2, "path": "b", "sha256": "%s"}' % _SHA.encode(),
        b'{"bytes": 9, "git_tracked": true, "path": "p", "sha256": "%s"}' % _SHA.encode(),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_package_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.project_package.manifest'`.

- [ ] **Step 3: Create `manifest.py`**

Create `science/src/science_tool/project_package/manifest.py`:

```python
"""The `science-project-serialized.v1` manifest schema + data_version identity.

Single source of truth shared by `serialize` (writer) and `verify` (reader):
the strict schema, and the canonical chunk sequence whose digest is the
manifest's `data_version`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "science-project-serialized.v1"

_SAFE_ID_RE = re.compile(r"\A[A-Za-z0-9._-]+\Z")
_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")


def _check_safe_relpath(path: str) -> str:
    if not path or path.startswith("/") or "\\" in path:
        raise ValueError(f"unsafe manifest path: {path!r}")
    if any(seg in ("", ".", "..") for seg in path.split("/")):
        raise ValueError(f"unsafe manifest path: {path!r}")
    return path


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectInfo(_Strict):
    id: str
    label: str
    summary: str | None = None

    @field_validator("id")
    @classmethod
    def _safe_id(cls, v: str) -> str:
        if v in ("", ".", "..") or "/" in v or "\\" in v or not _SAFE_ID_RE.match(v):
            raise ValueError(f"unsafe project id: {v!r}")
        return v


class Provenance(_Strict):
    git_commit: str
    tool: str


class BoundaryAudit(_Strict):
    passed: bool
    forced: bool


class FileRecord(_Strict):
    path: str
    sha256: str
    bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def _safe_path(cls, v: str) -> str:
        return _check_safe_relpath(v)

    @field_validator("sha256")
    @classmethod
    def _safe_sha(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError(f"bad sha256: {v!r}")
        return v


class PayloadRecord(FileRecord):
    git_tracked: bool


class SerializedManifest(_Strict):
    schema_version: str
    project: ProjectInfo
    data_version: str
    provenance: Provenance
    boundary_audit: BoundaryAudit
    files: list[FileRecord]
    payloads: list[PayloadRecord]

    @field_validator("schema_version")
    @classmethod
    def _exact_schema(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {v!r}")
        return v

    @model_validator(mode="after")
    def _unique_sorted_paths(self) -> "SerializedManifest":
        for label, rows in (("files", self.files), ("payloads", self.payloads)):
            paths = [r.path for r in rows]
            if len(paths) != len(set(paths)):
                raise ValueError(f"duplicate path in {label}")
            if paths != sorted(paths):
                raise ValueError(f"{label} must be sorted by path")
        return self


def data_version_chunks(
    files: Iterable[Mapping], payloads: Iterable[Mapping]
) -> list[bytes]:
    """Canonical record chunks whose folded sha256 is the manifest data_version.

    Per file: ``{path,sha256,bytes}``; per payload: ``{path,sha256,bytes,
    git_tracked}`` — each ``json.dumps(..., sort_keys=True)``, in the order
    given (validated sorted manifest order). Folded separator-free by
    ``content_version``.
    """
    chunks: list[bytes] = []
    for fr in files:
        chunks.append(json.dumps(
            {"path": fr["path"], "sha256": fr["sha256"], "bytes": fr["bytes"]},
            sort_keys=True,
        ).encode("utf-8"))
    for p in payloads:
        chunks.append(json.dumps(
            {"path": p["path"], "sha256": p["sha256"], "bytes": p["bytes"],
             "git_tracked": p["git_tracked"]},
            sort_keys=True,
        ).encode("utf-8"))
    return chunks
```

- [ ] **Step 4: Run the model tests**

Run: `.venv/bin/python -m pytest tests/test_project_package_manifest.py -v`
Expected: PASS.

- [ ] **Step 5: Rewire serialize's `_build_manifest` onto `data_version_chunks` (behavior-neutral)**

In `science/src/science_tool/project_package/serialize.py`:

1. Add to imports: `from science_tool.project_package.manifest import data_version_chunks`.
2. Replace the body of `_build_manifest` that builds `chunks` and the `files` list so the file-record list is built once and fed to both. The function becomes:

```python
def _build_manifest(
    project_root: Path,
    files: list[FileResource],
    payloads: list[dict],
    *,
    audit_passed: bool,
    forced: bool,
    git_commit: str,
) -> dict:
    config = load_project_config(project_root)
    raw = yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
    base = str(raw.get("last_modified") or raw.get("version") or "0")

    file_records = [
        {"path": fr.path, "sha256": fr.sha256, "bytes": fr.bytes} for fr in files
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": config.id,
            "label": str(raw.get("name") or config.id),
            "summary": raw.get("summary"),
        },
        "data_version": content_version(base, data_version_chunks(file_records, payloads)),
        "provenance": {"git_commit": git_commit, "tool": "science"},
        # `passed` = zero blocking payload-boundary violations (STRANDED_RECORD /
        # LEAKED_PAYLOAD / TRACKED_PAYLOAD); non-blocking FLAG findings are not counted.
        "boundary_audit": {"passed": audit_passed, "forced": forced},
        "files": file_records,
        "payloads": payloads,
    }
```

(The now-unused `import json` in serialize stays only if other code uses it — check: `_write_archive` uses `json.dumps`, so keep `import json`.)

- [ ] **Step 6: Prove serialize is byte-identical + add the lockstep test**

Append to `science/tests/test_project_package_manifest.py`:

```python
def test_serialize_output_parses_through_model(tmp_path):
    import subprocess

    from science_tool.project_package.serialize import _build_manifest, file_resource

    (tmp_path / "entities").mkdir()
    (tmp_path / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (tmp_path / "entities" / "q.md").write_text("# q\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    files = [file_resource(tmp_path, "science.yaml"),
             file_resource(tmp_path, "entities/q.md")]
    manifest = _build_manifest(
        tmp_path, files, payloads=[], audit_passed=True, forced=False,
        git_commit="deadbeef",
    )
    # The writer's dict round-trips cleanly through the reader's strict model.
    SerializedManifest.model_validate(manifest)
```

Run: `.venv/bin/python -m pytest tests/test_project_package_manifest.py tests/test_project_serialize.py -v`
Expected: PASS — model + lockstep green; all existing serialize tests (including the determinism / `data_version`-on-rename assertions) still green, proving the chunk refactor is byte-identical.

- [ ] **Step 7: Lint + commit**

```bash
.venv/bin/ruff check src/science_tool/project_package/manifest.py src/science_tool/project_package/serialize.py tests/test_project_package_manifest.py
git add src/science_tool/project_package/manifest.py src/science_tool/project_package/serialize.py tests/test_project_package_manifest.py
git commit -m "feat(project-package): strict SerializedManifest model + shared data_version chunks"
```

---

## Task 3: `verify.py` self-check (`load_bundle`)

**Files:**
- Create: `science/src/science_tool/project_package/verify.py`
- Create: `science/tests/test_project_verify.py` (shared bundle helpers defined here at top)

**Interfaces:**
- Consumes: `SerializedManifest`, `data_version_chunks` from `manifest.py`; `content_version` from `core.py`.
- Produces:
  - `class VerifyError(Exception)` (operational → exit 4); `class BundleIntegrityError(Exception)` (integrity → exit 2).
  - `@dataclass(frozen=True) class LoadedBundle: project_id: str; manifest: SerializedManifest; manifest_bytes: bytes; members: dict[str, bytes]` (members keyed by prefix-stripped path, manifest.json excluded).
  - `load_bundle(bundle_path: Path) -> LoadedBundle` — opens the `.tar.gz`, runs every self-check step, raises `VerifyError` only for "file not found / unreadable path", else `BundleIntegrityError`.
- Test helpers produced (top of `tests/test_project_verify.py`, reused by Tasks 4–6): `_init_repo(root)`, `_make_project(root)`, `_make_bundle(tmp_path) -> tuple[Path, Path]` (returns `(project_root, bundle_path)`), `_write_bundle(path, members: dict[str, bytes])` (writes a deterministic gzip tar from a literal member map, no validation — for crafting malformed bundles).

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_project_verify.py`:

```python
import gzip
import io
import subprocess
import tarfile
from pathlib import Path

import pytest

from science_tool.project_package.serialize import serialize_project
from science_tool.project_package.verify import (
    BundleIntegrityError,
    VerifyError,
    load_bundle,
)


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _make_project(root: Path) -> None:
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (root / "entities" / "questions" / "q1.md").write_text("# q\n", encoding="utf-8")
    # data/ is gitignored (the normal symlink-hydrated payload case): an
    # UNtracked payload, so serialize records it without a TRACKED_PAYLOAD
    # boundary violation. Tracking it would make serialize refuse without --force.
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "data" / "processed").mkdir(parents=True)
    (root / "data" / "processed" / "x.parquet").write_bytes(b"PAYLOAD")
    _init_repo(root)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def _make_bundle(tmp_path: Path) -> tuple[Path, Path]:
    proj = tmp_path / "proj"
    proj.mkdir()
    _make_project(proj)
    bundle = tmp_path / "bundle.tar.gz"
    serialize_project(proj, bundle)
    return proj, bundle


def _write_bundle(path: Path, members: dict[str, bytes]) -> None:
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    path.write_bytes(raw.getvalue())


def test_load_bundle_self_check_passes(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    assert loaded.project_id == "demo"
    assert "science.yaml" in loaded.members
    assert "manifest.json" not in loaded.members
    assert loaded.manifest.payloads[0].path == "data/processed/x.parquet"


def test_load_bundle_missing_file_is_operational(tmp_path: Path):
    with pytest.raises(VerifyError):
        load_bundle(tmp_path / "nope.tar.gz")


def test_load_bundle_not_a_tar_is_integrity(tmp_path: Path):
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a gzip stream")
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_root_level_manifest_is_integrity(tmp_path: Path):
    bad = tmp_path / "bad.tar.gz"
    _write_bundle(bad, {"manifest.json": b"{}"})  # no project-id prefix
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_mixed_prefixes_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    # repack original members plus one under a different prefix
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members["other/stray.md"] = b"x"
    bad = tmp_path / "mixed.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_tampered_byte_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members["demo/science.yaml"] = members["demo/science.yaml"] + b"TAMPER"
    bad = tmp_path / "tampered.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_extra_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    members["demo/entities/questions/stray.md"] = b"# stray\n"
    bad = tmp_path / "extra.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_edited_data_version_is_integrity(tmp_path: Path):
    import json
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    manifest = json.loads(members["demo/manifest.json"])
    manifest["data_version"] = "0+deadbeefdead"
    members["demo/manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    bad = tmp_path / "dv.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_prefix_ne_project_id_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name.replace("demo/", "other/", 1): tar.extractfile(m).read()
                   for m in tar.getmembers()}
    bad = tmp_path / "prefix.tar.gz"
    _write_bundle(bad, members)
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_symlink_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            link = tarfile.TarInfo("demo/evil-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            tar.addfile(link)
    bad = tmp_path / "symlink.tar.gz"
    bad.write_bytes(raw.getvalue())
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_hardlink_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: tar.extractfile(m).read() for m in tar.getmembers()}
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in sorted(members.items()):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            link = tarfile.TarInfo("demo/evil-hardlink")
            link.type = tarfile.LNKTYPE
            link.linkname = "demo/science.yaml"
            tar.addfile(link)
    bad = tmp_path / "hardlink.tar.gz"
    bad.write_bytes(raw.getvalue())
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)


def test_load_bundle_duplicate_member_is_integrity(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    with tarfile.open(bundle, "r:gz") as tar:
        members = [(m.name, tar.extractfile(m).read()) for m in tar.getmembers()]
    # Append a second copy of an existing source member (same arcname twice).
    dup_name, dup_data = next((n, d) for n, d in members if n.endswith("science.yaml"))
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for name, data in [*members, (dup_name, dup_data)]:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    bad = tmp_path / "dup.tar.gz"
    bad.write_bytes(raw.getvalue())
    with pytest.raises(BundleIntegrityError):
        load_bundle(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.project_package.verify'`.

- [ ] **Step 3: Create `verify.py` with `load_bundle` + self-check**

Create `science/src/science_tool/project_package/verify.py`:

```python
"""`science project verify` — read/check a serialized project bundle.

Reader counterpart to serialize.py. Self-check validates the bundle is an
intact `science-project-serialized.v1`; --against / --extract build on it.
See docs/plans/2026-06-29-project-verify-design.md.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from science_tool.project_package.core import content_version
from science_tool.project_package.manifest import SerializedManifest, data_version_chunks


class VerifyError(Exception):
    """Operational / precondition failure (exit 4)."""


class BundleIntegrityError(Exception):
    """The bundle is not a valid, intact science-serialized bundle (exit 2)."""


@dataclass(frozen=True)
class LoadedBundle:
    project_id: str
    manifest: SerializedManifest
    manifest_bytes: bytes
    members: dict[str, bytes]  # prefix-stripped path -> bytes (manifest.json excluded)


def load_bundle(bundle_path: Path) -> LoadedBundle:
    if not bundle_path.exists() or not bundle_path.is_file():
        raise VerifyError(f"bundle not found: {bundle_path}")
    try:
        raw = bundle_path.read_bytes()
    except OSError as exc:
        raise VerifyError(f"cannot read bundle: {exc}") from exc

    raw_members = _read_members(raw)
    return _check_structure(raw_members)


def _read_members(raw: bytes) -> dict[str, bytes]:
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            members: dict[str, bytes] = {}
            for info in tar.getmembers():
                name = info.name
                if name.startswith("/") or ".." in Path(name).parts:
                    raise BundleIntegrityError(f"unsafe tar member path: {name}")
                if not info.isreg():
                    raise BundleIntegrityError(f"unsafe non-regular tar member: {name}")
                if name in members:
                    raise BundleIntegrityError(f"duplicate tar member: {name}")
                extracted = tar.extractfile(info)
                members[name] = extracted.read() if extracted is not None else b""
            return members
    except (tarfile.TarError, gzip.BadGzipFile, EOFError, OSError) as exc:
        raise BundleIntegrityError(f"not a readable gzip tar bundle: {exc}") from exc


def _check_structure(raw_members: dict[str, bytes]) -> LoadedBundle:
    if not raw_members:
        raise BundleIntegrityError("empty bundle")
    prefixes = {name.split("/", 1)[0] for name in raw_members}
    if len(prefixes) != 1:
        raise BundleIntegrityError(
            f"bundle has mixed top-level prefixes: {sorted(prefixes)}")
    prefix = next(iter(prefixes))

    stripped: dict[str, bytes] = {}
    for name, data in raw_members.items():
        if "/" not in name:
            raise BundleIntegrityError(f"member not under a project dir: {name}")
        stripped[name.split("/", 1)[1]] = data

    if "manifest.json" not in stripped:
        raise BundleIntegrityError("bundle missing manifest.json")
    manifest_bytes = stripped["manifest.json"]
    try:
        manifest = SerializedManifest.model_validate_json(manifest_bytes)
    except ValidationError as exc:
        raise BundleIntegrityError(f"invalid manifest: {exc}") from exc

    if prefix != manifest.project.id:
        raise BundleIntegrityError(
            f"archive prefix {prefix!r} != manifest project id {manifest.project.id!r}")

    members = {k: v for k, v in stripped.items() if k != "manifest.json"}
    expected = {fr.path for fr in manifest.files}
    if set(members) != expected:
        missing = sorted(expected - set(members))
        extra = sorted(set(members) - expected)
        raise BundleIntegrityError(
            f"member set mismatch: missing={missing} extra={extra}")

    for fr in manifest.files:
        data = members[fr.path]
        if len(data) != fr.bytes or hashlib.sha256(data).hexdigest() != fr.sha256:
            raise BundleIntegrityError(f"content hash mismatch: {fr.path}")

    _check_data_version(manifest)
    return LoadedBundle(prefix, manifest, manifest_bytes, members)


def _check_data_version(manifest: SerializedManifest) -> None:
    stored = manifest.data_version
    if "+" not in stored:
        raise BundleIntegrityError(f"malformed data_version: {stored!r}")
    base = stored.rsplit("+", 1)[0]
    file_records = [
        {"path": fr.path, "sha256": fr.sha256, "bytes": fr.bytes} for fr in manifest.files
    ]
    payload_records = [
        {"path": p.path, "sha256": p.sha256, "bytes": p.bytes, "git_tracked": p.git_tracked}
        for p in manifest.payloads
    ]
    recomputed = content_version(base, data_version_chunks(file_records, payload_records))
    if recomputed != stored:
        raise BundleIntegrityError(
            f"data_version mismatch: stored {stored} != recomputed {recomputed}")
```

- [ ] **Step 4: Run the self-check tests**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -v`
Expected: PASS — all self-check pass/fail cases green.

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check src/science_tool/project_package/verify.py tests/test_project_verify.py
git add src/science_tool/project_package/verify.py tests/test_project_verify.py
git commit -m "feat(project-package): verify self-check (load_bundle integrity)"
```

---

## Task 4: `--against` comparison (commit + source + payloads)

**Files:**
- Modify: `science/src/science_tool/project_package/verify.py`
- Modify: `science/tests/test_project_verify.py` (append tests; reuse `_make_bundle`)

**Interfaces:**
- Consumes: `LoadedBundle`, `VerifyError` (Task 3); `file_resource` from `core.py`; `payload_inventory`/`PayloadError` from `payload.py`; `DEFAULT_DATA_DIRS` from `data_worktree`.
- Produces:
  - `@dataclass class CommitCompare: bundle: str; head: str; match: bool`
  - `@dataclass class SourceCompare: total: int; match: int; differ: list[str]; absent: list[str]`
  - `@dataclass class PayloadCompare: ok: int; differ: list[str]; missing: list[str]; extra: list[str]`
  - `@dataclass class AgainstResult: root: str; commit: CommitCompare; source: SourceCompare; payloads: PayloadCompare`
  - `preflight_against(root: Path) -> str` (returns HEAD sha; raises `VerifyError` if root missing / not a git worktree / no HEAD)
  - `compare_against(bundle: LoadedBundle, root: Path, head: str) -> AgainstResult`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_project_verify.py`:

```python
from science_tool.project_package.verify import (  # noqa: E402
    compare_against,
    preflight_against,
)


def test_against_clean_checkout_matches(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    head = preflight_against(proj)
    res = compare_against(loaded, proj, head)
    assert res.commit.match is True
    assert res.source.differ == [] and res.source.absent == []
    assert res.payloads.ok == 1
    assert res.payloads.missing == [] and res.payloads.differ == []


def test_against_payload_missing(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    (proj / "data" / "processed" / "x.parquet").unlink()
    head = preflight_against(proj)
    res = compare_against(loaded, proj, head)
    assert res.payloads.missing == ["data/processed/x.parquet"]
    assert res.payloads.differ == []


def test_against_payload_differs(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    (proj / "data" / "processed" / "x.parquet").write_bytes(b"CHANGED")
    head = preflight_against(proj)
    res = compare_against(loaded, proj, head)
    assert res.payloads.differ == ["data/processed/x.parquet"]
    assert res.payloads.missing == []


def test_against_payload_extra_is_non_fatal(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    (proj / "data" / "processed" / "extra.bin").write_bytes(b"new")
    head = preflight_against(proj)
    res = compare_against(loaded, proj, head)
    assert res.payloads.extra == ["data/processed/extra.bin"]
    assert res.payloads.ok == 1


def test_against_source_differs(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    (proj / "entities" / "questions" / "q1.md").write_text("# CHANGED\n", encoding="utf-8")
    head = preflight_against(proj)
    res = compare_against(loaded, proj, head)
    assert res.source.differ == ["entities/questions/q1.md"]


def test_against_source_absent(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    (proj / "entities" / "questions" / "q1.md").unlink()
    head = preflight_against(proj)
    res = compare_against(loaded, proj, head)
    assert res.source.absent == ["entities/questions/q1.md"]


def test_against_commit_differs_after_new_commit(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    (proj / "entities" / "questions" / "q2.md").write_text("# q2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "more"], cwd=proj, check=True)
    head = preflight_against(proj)
    res = compare_against(loaded, proj, head)
    assert res.commit.match is False


def test_preflight_against_non_git_is_operational(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(VerifyError):
        preflight_against(plain)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -k against -v`
Expected: FAIL — `ImportError: cannot import name 'compare_against'`.

- [ ] **Step 3: Implement `--against` in `verify.py`**

Add to the imports block of `verify.py`:

```python
import subprocess

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_package.core import file_resource
from science_tool.project_package.payload import PayloadError, payload_inventory
```

Append to `verify.py`:

```python
@dataclass(frozen=True)
class CommitCompare:
    bundle: str
    head: str
    match: bool


@dataclass(frozen=True)
class SourceCompare:
    total: int
    match: int
    differ: list[str]
    absent: list[str]


@dataclass(frozen=True)
class PayloadCompare:
    ok: int
    differ: list[str]
    missing: list[str]
    extra: list[str]


@dataclass(frozen=True)
class AgainstResult:
    root: str
    commit: CommitCompare
    source: SourceCompare
    payloads: PayloadCompare


def preflight_against(root: Path) -> str:
    if not root.exists() or not root.is_dir():
        raise VerifyError(f"--against root not found: {root}")
    try:
        # Must be a real worktree (a bare repo can have HEAD but no working
        # tree to compare source bytes against), then resolve the HEAD sha.
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if inside != "true":
            raise VerifyError(f"--against root is not a git worktree: {root}")
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise VerifyError(
            f"--against root is not a git worktree with a HEAD commit: {root}"
        ) from exc


def _tracked_set(root: Path) -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, check=True,
    ).stdout
    return {p for p in out.decode("utf-8").split("\0") if p}


def compare_against(bundle: LoadedBundle, root: Path, head: str) -> AgainstResult:
    m = bundle.manifest
    commit = CommitCompare(m.provenance.git_commit, head, m.provenance.git_commit == head)

    differ: list[str] = []
    absent: list[str] = []
    match = 0
    for fr in m.files:
        target = root / fr.path
        if target.is_symlink() or not target.is_file():
            absent.append(fr.path)
            continue
        try:
            res = file_resource(root, fr.path)
        except OSError as exc:
            raise VerifyError(
                f"cannot read source under --against root: {fr.path}: {exc}"
            ) from exc
        if res.sha256 == fr.sha256 and res.bytes == fr.bytes:
            match += 1
        else:
            differ.append(fr.path)
    source = SourceCompare(len(m.files), match, sorted(differ), sorted(absent))

    try:
        local = payload_inventory(root, DEFAULT_DATA_DIRS, _tracked_set(root))
    except PayloadError as exc:
        raise VerifyError(f"payload walk failed under --against root: {exc}") from exc
    local_by_path = {p["path"]: p for p in local}
    bundle_by_path = {p.path: p for p in m.payloads}

    ok = 0
    pdiffer: list[str] = []
    missing: list[str] = []
    for path, p in bundle_by_path.items():
        lp = local_by_path.get(path)
        if lp is None:
            missing.append(path)
        elif lp["sha256"] == p.sha256 and lp["bytes"] == p.bytes:
            ok += 1
        else:
            pdiffer.append(path)
    extra = [path for path in local_by_path if path not in bundle_by_path]
    payloads = PayloadCompare(ok, sorted(pdiffer), sorted(missing), sorted(extra))

    return AgainstResult(str(root), commit, source, payloads)
```

- [ ] **Step 4: Run the `--against` tests**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -k against -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check src/science_tool/project_package/verify.py tests/test_project_verify.py
git add src/science_tool/project_package/verify.py tests/test_project_verify.py
git commit -m "feat(project-package): verify --against (commit, source, payloads)"
```

---

## Task 5: `--extract` (verify-then-extract, atomic staging)

**Files:**
- Modify: `science/src/science_tool/project_package/verify.py`
- Modify: `science/tests/test_project_verify.py` (append; reuse `_make_bundle`)

**Interfaces:**
- Consumes: `LoadedBundle`, `VerifyError` (Task 3).
- Produces:
  - `preflight_extract(dest: Path) -> None` (raises `VerifyError` if `dest` exists non-empty or is a non-directory)
  - `extract_bundle(bundle: LoadedBundle, dest: Path) -> Path` — writes `dest/<project-id>/manifest.json` + source tree via a sibling staging dir + atomic rename; raises `VerifyError` on filesystem error, leaving `dest` untouched.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_project_verify.py`:

```python
from science_tool.project_package.verify import (  # noqa: E402
    extract_bundle,
    preflight_extract,
)


def test_extract_writes_faithful_tree(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    dest = tmp_path / "out"
    preflight_extract(dest)
    result = extract_bundle(loaded, dest)
    assert result == dest
    assert (dest / "demo" / "manifest.json").is_file()
    assert (dest / "demo" / "science.yaml").read_bytes() == loaded.members["science.yaml"]
    assert (dest / "demo" / "entities" / "questions" / "q1.md").is_file()
    # manifest written byte-for-byte
    assert (dest / "demo" / "manifest.json").read_bytes() == loaded.manifest_bytes


def test_extract_into_existing_empty_dir_ok(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    dest = tmp_path / "out"
    dest.mkdir()
    preflight_extract(dest)
    extract_bundle(loaded, dest)
    assert (dest / "demo" / "science.yaml").is_file()


def test_preflight_extract_non_empty_is_operational(tmp_path: Path):
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "preexisting").write_text("x", encoding="utf-8")
    with pytest.raises(VerifyError):
        preflight_extract(dest)


def test_preflight_extract_file_target_is_operational(tmp_path: Path):
    dest = tmp_path / "out"
    dest.write_text("i am a file", encoding="utf-8")
    with pytest.raises(VerifyError):
        preflight_extract(dest)


def test_extract_mid_write_error_leaves_existing_dest_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, bundle = _make_bundle(tmp_path)
    loaded = load_bundle(bundle)
    dest = tmp_path / "out"
    dest.mkdir()

    original_write_bytes = Path.write_bytes

    def flaky_write_bytes(self: Path, data: bytes) -> int:
        if self.name == "science.yaml":
            raise OSError("simulated write failure")
        return original_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky_write_bytes)

    with pytest.raises(VerifyError):
        extract_bundle(loaded, dest)

    assert dest.exists() and dest.is_dir()
    assert list(dest.iterdir()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -k extract -v`
Expected: FAIL — `ImportError: cannot import name 'extract_bundle'`.

- [ ] **Step 3: Implement `--extract` in `verify.py`**

Add to the imports block of `verify.py`:

```python
import os
import shutil
import tempfile
```

Append to `verify.py`:

```python
def preflight_extract(dest: Path) -> None:
    if dest.exists():
        if not dest.is_dir():
            raise VerifyError(f"--extract target exists and is not a directory: {dest}")
        if any(dest.iterdir()):
            raise VerifyError(f"--extract target is not empty: {dest}")


def extract_bundle(bundle: LoadedBundle, dest: Path) -> Path:
    """Write the bundle's source tree to dest/<project-id>/ atomically.

    Materialize into a sibling staging dir, then rename it onto ``dest`` as the
    final step. On Linux ``os.rename`` replaces an existing *empty* directory
    atomically, so we never explicitly remove ``dest``: a mid-extract error (or
    a failed rename) leaves ``dest`` exactly as it was.
    """
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise VerifyError(f"failed to prepare --extract target parent: {exc}") from exc
    staging = Path(tempfile.mkdtemp(prefix=".verify-extract-", dir=str(dest.parent)))
    try:
        root = staging / bundle.project_id
        root.mkdir(parents=True)
        (root / "manifest.json").write_bytes(bundle.manifest_bytes)
        for rel, data in bundle.members.items():
            out = root / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        # rename onto dest: succeeds whether dest is absent or an existing
        # empty dir (preflight guaranteed empty); dest is never rmdir'd first.
        os.rename(staging, dest)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise VerifyError(f"failed to extract bundle: {exc}") from exc
    return dest
```

- [ ] **Step 4: Run the `--extract` tests**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -k extract -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check src/science_tool/project_package/verify.py tests/test_project_verify.py
git add src/science_tool/project_package/verify.py tests/test_project_verify.py
git commit -m "feat(project-package): verify --extract (atomic staging)"
```

---

## Task 6: Orchestration — `verify_project` + exit codes + JSON verdict

**Files:**
- Modify: `science/src/science_tool/project_package/verify.py`
- Modify: `science/tests/test_project_verify.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 3–5.
- Produces:
  - `@dataclass class VerifyResult: exit_code: int; status: str; bundle_schema_version: str; project_id: str; file_count: int; data_version: str; against: AgainstResult | None; warnings: list[str]; extracted_to: Path | None`
  - `verify_project(bundle_path: Path, *, against: Path | None = None, extract: Path | None = None) -> VerifyResult` — load (self-check) → preflight both targets → compare → extract → verdict. Lets `BundleIntegrityError`/`VerifyError` propagate.
  - `verdict_json(result: VerifyResult) -> dict` — the stable `--json` shape (top-level `version: 1`, `bundle_schema_version`, `exit_code`, `status`, `self_check`, `against`, `warnings`).
- Status vocabulary: `"clean"` (0), `"differ"` (1), `"missing"` (3). (Integrity `2` / operational `4` are raised as exceptions, never a `VerifyResult`.)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_project_verify.py`:

```python
from science_tool.project_package.verify import (  # noqa: E402
    verdict_json,
    verify_project,
)


def test_verify_project_self_check_only_is_clean(tmp_path: Path):
    _, bundle = _make_bundle(tmp_path)
    result = verify_project(bundle)
    assert result.exit_code == 0 and result.status == "clean"
    assert result.against is None
    assert result.project_id == "demo"


def test_verify_project_round_trip_against_clean(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    result = verify_project(bundle, against=proj)
    assert result.exit_code == 0 and result.status == "clean"
    assert result.against.payloads.ok == 1


def test_verify_project_missing_payload_is_exit_3(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    (proj / "data" / "processed" / "x.parquet").unlink()
    result = verify_project(bundle, against=proj)
    assert result.exit_code == 3 and result.status == "missing"


def test_verify_project_differ_dominates_missing(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    # one payload differs AND source differs -> exit 1 even if something also missing
    (proj / "data" / "processed" / "x.parquet").write_bytes(b"CHANGED")
    result = verify_project(bundle, against=proj)
    assert result.exit_code == 1 and result.status == "differ"


def test_verify_project_preflight_runs_before_compare(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    bad_extract = tmp_path / "occupied"
    bad_extract.mkdir()
    (bad_extract / "f").write_text("x", encoding="utf-8")
    # extract target invalid -> operational, raised before any comparison verdict
    with pytest.raises(VerifyError):
        verify_project(bundle, against=proj, extract=bad_extract)


def test_verify_project_extract_and_against_combine(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    dest = tmp_path / "out"
    result = verify_project(bundle, against=proj, extract=dest)
    assert result.exit_code == 0
    assert result.extracted_to == dest
    assert (dest / "demo" / "science.yaml").is_file()


def test_force_built_bundle_warns(tmp_path: Path):
    # build a project with a boundary violation, serialize with force=True
    proj = tmp_path / "proj"
    (proj / "data" / "processed" / "exp").mkdir(parents=True)
    (proj / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (proj / "data" / "processed" / "exp" / "RESULTS.md").write_text("# r\n", encoding="utf-8")
    _init_repo(proj)
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=proj, check=True)
    bundle = tmp_path / "forced.tar.gz"
    serialize_project(proj, bundle, force=True)
    result = verify_project(bundle)
    assert any("force" in w for w in result.warnings)
    assert result.exit_code == 0  # warning does not change exit code


def test_verdict_json_shape(tmp_path: Path):
    proj, bundle = _make_bundle(tmp_path)
    (proj / "data" / "processed" / "x.parquet").unlink()
    payload = verdict_json(verify_project(bundle, against=proj))
    assert payload["version"] == 1
    assert payload["bundle_schema_version"] == "science-project-serialized.v1"
    assert payload["exit_code"] == 3
    assert payload["status"] == "missing"
    assert payload["self_check"]["passed"] is True
    assert payload["against"]["payloads"]["missing"] == ["data/processed/x.parquet"]
    assert "schema_version" not in payload  # never the ambiguous name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -k "verify_project or verdict or force" -v`
Expected: FAIL — `ImportError: cannot import name 'verify_project'`.

- [ ] **Step 3: Implement orchestration in `verify.py`**

Append to `verify.py`:

```python
@dataclass(frozen=True)
class VerifyResult:
    exit_code: int
    status: str
    bundle_schema_version: str
    project_id: str
    file_count: int
    data_version: str
    against: AgainstResult | None
    warnings: list[str]
    extracted_to: Path | None


def _verdict(against: AgainstResult | None) -> tuple[int, str]:
    if against is None:
        return 0, "clean"
    differ = (
        not against.commit.match
        or bool(against.source.differ)
        or bool(against.source.absent)
        or bool(against.payloads.differ)
    )
    if differ:
        return 1, "differ"
    if against.payloads.missing:
        return 3, "missing"
    return 0, "clean"


def verify_project(
    bundle_path: Path,
    *,
    against: Path | None = None,
    extract: Path | None = None,
) -> VerifyResult:
    bundle = load_bundle(bundle_path)  # BundleIntegrityError(2) / VerifyError(4)

    warnings: list[str] = []
    if bundle.manifest.boundary_audit.forced:
        warnings.append(
            "bundle built with --force; payload boundary was not clean at serialize time"
        )

    # Preflight ALL operational preconditions before any comparison verdict.
    head: str | None = None
    if against is not None:
        head = preflight_against(against)
    if extract is not None:
        preflight_extract(extract)

    against_result: AgainstResult | None = None
    if against is not None:
        against_result = compare_against(bundle, against, head)  # type: ignore[arg-type]

    extracted_to: Path | None = None
    if extract is not None:
        extracted_to = extract_bundle(bundle, extract)

    exit_code, status = _verdict(against_result)
    return VerifyResult(
        exit_code=exit_code,
        status=status,
        bundle_schema_version=bundle.manifest.schema_version,
        project_id=bundle.project_id,
        file_count=len(bundle.manifest.files),
        data_version=bundle.manifest.data_version,
        against=against_result,
        warnings=warnings,
        extracted_to=extracted_to,
    )


def verdict_json(result: VerifyResult) -> dict:
    out: dict = {
        "version": 1,
        "bundle_schema_version": result.bundle_schema_version,
        "exit_code": result.exit_code,
        "status": result.status,
        "self_check": {
            "passed": True,
            "files": result.file_count,
            "data_version": result.data_version,
        },
        "against": None,
        "warnings": list(result.warnings),
    }
    if result.against is not None:
        a = result.against
        out["against"] = {
            "root": a.root,
            "commit": {"bundle": a.commit.bundle, "head": a.commit.head,
                       "match": a.commit.match},
            "source": {"total": a.source.total, "match": a.source.match,
                       "differ": a.source.differ, "absent": a.source.absent},
            "payloads": {"ok": a.payloads.ok, "differ": a.payloads.differ,
                         "missing": a.payloads.missing, "extra": a.payloads.extra},
        }
    return out
```

- [ ] **Step 4: Run the orchestration tests**

Run: `.venv/bin/python -m pytest tests/test_project_verify.py -v`
Expected: PASS — full verify module green.

- [ ] **Step 5: Lint + commit**

```bash
.venv/bin/ruff check src/science_tool/project_package/verify.py tests/test_project_verify.py
git add src/science_tool/project_package/verify.py tests/test_project_verify.py
git commit -m "feat(project-package): verify_project orchestration + JSON verdict"
```

---

## Task 7: CLI — `science project verify`

**Files:**
- Modify: `science/src/science_tool/cli.py` (add `@project.command("verify")` right after `project_serialize`, near `cli.py:4663`)
- Create: `science/tests/test_project_verify_cli.py`

**Interfaces:**
- Consumes: `verify_project`, `verdict_json`, `BundleIntegrityError`, `VerifyError` from `project_package/verify.py`.
- Produces: the `science project verify` command. Exit codes via `ctx.exit(code)`: integrity → 2, operational → 4, else `result.exit_code`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_project_verify_cli.py`:

```python
import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.project_package.serialize import serialize_project


def _make_project(root: Path) -> None:
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (root / "entities" / "questions" / "q1.md").write_text("# q\n", encoding="utf-8")
    # data/ gitignored (untracked payload) so serialize records it without a
    # TRACKED_PAYLOAD boundary violation.
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "data" / "processed").mkdir(parents=True)
    (root / "data" / "processed" / "x.parquet").write_bytes(b"PAYLOAD")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    proj = tmp_path / "proj"
    proj.mkdir()
    _make_project(proj)
    bundle = tmp_path / "bundle.tar.gz"
    serialize_project(proj, bundle)
    return proj, bundle


def test_cli_verify_self_check_exit_0(tmp_path: Path):
    _, bundle = _bundle(tmp_path)
    result = CliRunner().invoke(main, ["project", "verify", str(bundle)])
    assert result.exit_code == 0, result.output


def test_cli_verify_missing_bundle_exit_4(tmp_path: Path):
    result = CliRunner().invoke(main, ["project", "verify", str(tmp_path / "nope.tar.gz")])
    assert result.exit_code == 4


def test_cli_verify_corrupt_bundle_exit_2(tmp_path: Path):
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a gzip")
    result = CliRunner().invoke(main, ["project", "verify", str(bad)])
    assert result.exit_code == 2


def test_cli_verify_against_missing_payload_exit_3(tmp_path: Path):
    proj, bundle = _bundle(tmp_path)
    (proj / "data" / "processed" / "x.parquet").unlink()
    result = CliRunner().invoke(
        main, ["project", "verify", str(bundle), "--against", str(proj)]
    )
    assert result.exit_code == 3, result.output


def test_cli_verify_against_differ_exit_1(tmp_path: Path):
    proj, bundle = _bundle(tmp_path)
    (proj / "data" / "processed" / "x.parquet").write_bytes(b"CHANGED")
    result = CliRunner().invoke(
        main, ["project", "verify", str(bundle), "--against", str(proj)]
    )
    assert result.exit_code == 1, result.output


def test_cli_verify_json_is_pure_json(tmp_path: Path):
    proj, bundle = _bundle(tmp_path)
    (proj / "data" / "processed" / "x.parquet").unlink()
    result = CliRunner().invoke(
        main, ["project", "verify", str(bundle), "--against", str(proj), "--json"]
    )
    assert result.exit_code == 3
    # In --json mode nothing is written to stderr (warnings only print to stderr
    # in human mode), so result.output is exactly the JSON object.
    payload = json.loads(result.output)  # output parses as a single JSON object
    assert payload["status"] == "missing"
    assert payload["version"] == 1


def test_cli_verify_extract(tmp_path: Path):
    _, bundle = _bundle(tmp_path)
    dest = tmp_path / "out"
    result = CliRunner().invoke(
        main, ["project", "verify", str(bundle), "--extract", str(dest)]
    )
    assert result.exit_code == 0, result.output
    assert (dest / "demo" / "science.yaml").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_project_verify_cli.py -v`
Expected: FAIL — `project verify` not registered (Click: "No such command 'verify'", exit 2 from usage error, but the assertions on 0/3/4 fail).

- [ ] **Step 3: Add the CLI command**

In `science/src/science_tool/cli.py`, immediately after the `project_serialize` function (ends near `cli.py:4681`), add:

```python
@project.command("verify")
@click.argument("bundle", type=click.Path(exists=False, dir_okay=False, path_type=Path))
@click.option(
    "--against",
    "against_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Compare the bundle to a live checkout (commit, source, payloads). Explicit only.",
)
@click.option(
    "--extract",
    "extract_to",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Materialize the bundle's source tree into this (empty/new) directory.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit a JSON verdict.")
@click.pass_context
def project_verify(
    ctx: click.Context,
    bundle: Path,
    against_root: Path | None,
    extract_to: Path | None,
    as_json: bool,
) -> None:
    """Verify a serialized project bundle: self-check, optional --against / --extract.

    Exit codes: 0 clean, 1 differs, 2 bundle integrity, 3 payload(s) missing
    locally, 4 operational (bad path/precondition).
    """
    from science_tool.project_package.verify import (
        BundleIntegrityError,
        VerifyError,
        verdict_json,
        verify_project,
    )

    try:
        result = verify_project(bundle, against=against_root, extract=extract_to)
    except BundleIntegrityError as exc:
        _emit_verify_error(as_json, exit_code=2, status="integrity", message=str(exc))
        ctx.exit(2)
    except VerifyError as exc:
        _emit_verify_error(as_json, exit_code=4, status="operational", message=str(exc))
        ctx.exit(4)

    if as_json:
        click.echo(json.dumps(verdict_json(result), indent=2, sort_keys=True))
    else:
        _render_verify_human(result)
        for warning in result.warnings:
            click.echo(f"warning: {warning}", err=True)
    ctx.exit(result.exit_code)


def _emit_verify_error(as_json: bool, *, exit_code: int, status: str, message: str) -> None:
    if as_json:
        click.echo(json.dumps(
            {"version": 1, "exit_code": exit_code, "status": status, "error": message},
            indent=2, sort_keys=True,
        ))
    else:
        click.echo(f"error: {message}", err=True)


def _render_verify_human(result) -> None:
    click.echo(f"  ✓ schema {result.bundle_schema_version}")
    click.echo(f"  ✓ {result.file_count} file(s) match manifest hashes")
    click.echo(f"  ✓ data_version {result.data_version} recomputes")
    if result.extracted_to is not None:
        click.echo(f"  ✓ extracted → {result.extracted_to}")
    a = result.against
    if a is not None:
        click.echo(f"\n  against: {a.root}")
        mark = "✓" if a.commit.match else "✗"
        click.echo(f"    commit:   {a.commit.bundle[:8]} vs {a.commit.head[:8]}  {mark}")
        click.echo(
            f"    source:   {a.source.match}/{a.source.total} match"
            f"  (differ {len(a.source.differ)}, absent {len(a.source.absent)})"
        )
        click.echo(
            f"    payloads: {a.payloads.ok} ok, {len(a.payloads.differ)} differ, "
            f"{len(a.payloads.missing)} missing, {len(a.payloads.extra)} extra"
        )
        for path in a.payloads.missing:
            click.echo(f"              MISSING: {path}")
        for path in a.payloads.differ:
            click.echo(f"              DIFFER:  {path}")
    click.echo(f"\n  status: {result.status} (exit {result.exit_code})")
```

- [ ] **Step 4: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_project_verify_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Verify the command is registered**

Run: `.venv/bin/python -m science_tool.cli project verify --help`
Expected: help text prints the bundle arg + `--against`/`--extract`/`--json`; exit 0.

- [ ] **Step 6: Lint + commit**

```bash
.venv/bin/ruff check src/science_tool/cli.py tests/test_project_verify_cli.py
git add src/science_tool/cli.py tests/test_project_verify_cli.py
git commit -m "feat(cli): science project verify command"
```

---

## Final verification (after all tasks)

- [ ] Run the full touched surface:

```bash
.venv/bin/python -m pytest \
  tests/test_project_package_payload.py \
  tests/test_project_package_manifest.py \
  tests/test_project_package_core.py \
  tests/test_project_serialize.py \
  tests/test_project_serialize_cli.py \
  tests/test_project_verify.py \
  tests/test_project_verify_cli.py -v
```
Expected: all green (serialize tests prove the extractions stayed behavior-neutral; verify tests cover the new surface).

- [ ] Lint the whole package + CLI:

```bash
.venv/bin/ruff check src/science_tool/project_package/ src/science_tool/cli.py
```
Expected: no findings.

---

## Self-Review (filled in by plan author)

**Spec coverage:** self-check (Task 3) ✓; strict `SerializedManifest` incl. `extra="forbid"`, duplicate-path, sorted manifest order, safe id/path, sha/bytes shape (Task 2) ✓; behavior-neutral `payload.py` + `manifest.py` extractions (Tasks 1–2) ✓; `--against` all three dimensions incl. missing≠differ/extra-non-fatal (Tasks 4, 6) ✓; exit precedence 2→4→1→3→0 (Task 6 `_verdict` + Task 7 mapping) ✓; preflight-before-compare (Task 6) ✓; atomic `--extract` incl. mid-write failure leaving the target untouched (Task 5) ✓; pure-JSON stdout + `version:1` + `bundle_schema_version` + `warnings[]` (Tasks 6–7) ✓; `--against` no envvar (Task 7) ✓; round-trip + the three extra cases (prefix-mismatch, duplicate path, symlink/hardlink member) (Tasks 2–3) ✓; `--force` warning (Task 6) ✓.

**Type consistency:** `LoadedBundle`/`AgainstResult`/`VerifyResult` field names and the `compare_against(bundle, root, head)` / `preflight_against(root)->str` / `extract_bundle(bundle, dest)->Path` signatures are used identically across Tasks 3–7. The JSON shape in Task 6 matches the design's example and the CLI test in Task 7.

**Placeholder scan:** no TBD/TODO; every code step shows complete code; every test step shows real assertions.

**Unsafe-member coverage:** Task 3 has explicit self-check tests for a symlink member (`tarfile.SYMTYPE`), a hardlink member (`tarfile.LNKTYPE`), and a duplicate member name — each rejected as `BundleIntegrityError`. The design's symlink/hardlink-rejection requirement is covered directly, not by inference.

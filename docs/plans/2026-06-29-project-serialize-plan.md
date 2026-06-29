# Project Serialize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science project serialize`, producing a deterministic `.tar.gz` of a project's git-tracked source (entities + results, no `data/` payloads) plus a manifest that hash-inventories the excluded payloads.

**Architecture:** Extract the hashing/versioning primitives labnote and serialize share into a new `project_package/core.py` (behavior-neutral for labnote, enforced by a golden test). Build serialize as a file-level git operation in `project_package/serialize.py`. Close a boundary gap first: a new `TRACKED_PAYLOAD` audit quadrant so serialize's boundary gate is meaningful.

**Tech Stack:** Python 3.11+, `click` CLI (`science_tool/cli.py`), `pytest`, stdlib `tarfile`/`gzip`/`hashlib`/`os`/`subprocess`, `git`.

**Spec:** `docs/plans/2026-06-29-project-serialize-design.md`.

## Global Constraints

- Manifest schema id is exactly `science-project-serialized.v1`.
- Selection is **git-tracked only** (`git ls-files`). Source roots = `entities/`, `results/`. Top-level singles = `science.yaml`, `papers/references.bib`, `knowledge/graph.trig` (each only if tracked).
- `data/` is **never** copied into the archive; the `DEFAULT_DATA_DIRS` = `(data/raw, data/processed, data/external)` are walked only for the payload hash inventory.
- Payload entries use field name `git_tracked` (not "tracked"); normally `false`.
- `content_version()` is separator-free; labnote's `_data_version` digest must stay **byte-identical** after refactor.
- Manifest paths are archive-relative (no top-level project dir prefix). Inside the tar, members are prefixed with `<project-id>/`.
- Determinism: tar members sorted by arcname; every member `mtime=0`, `uid=gid=0`, `uname=gname=""`, mode `0o644`, type `REGTYPE`; no directory entries emitted; gzip stream `mtime=0`.
- `--project-root` defaults to `"."`, honors `SCIENCE_PROJECT_ROOT` envvar (house convention).
- `--force` bypasses **only** audit violations — never missing/untracked `science.yaml`, dirty source, invalid project config, non-git worktree, `--out`-inside-root, unreadable files, or payload-walk guard failures.
- Commit messages: NO `Co-Authored-By` trailers. Use `~/d/` (not absolute Dropbox paths) in any doc/code text.
- **Test env (worktree gotcha):** a fresh worktree's `uv` venv is empty. Run tests by reusing the main checkout's venv with worktree `PYTHONPATH`: `cd <worktree>/science && PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/python -m pytest <paths> -v`. The `Run:` lines below show the logical `pytest` invocation; apply this prefix in a worktree.

---

### Task 1: `TRACKED_PAYLOAD` audit quadrant (boundary prerequisite)

Close the gap where a payload tracked **inside** `data/` is not flagged, so serialize's gate catches it. Remediation is `git rm --cached` (untrack-in-place) — report-only, never an auto-move.

**Files:**
- Modify: `science/src/science_tool/data_audit.py` (the `Quadrant` enum ~L29-32; `_violation_for` ~L176-188)
- Test: `science/tests/test_data_audit.py`

**Interfaces:**
- Consumes: existing `audit_project(project_root, policy=DEFAULT_DATA_POLICY, data_dirs=DEFAULT_DATA_DIRS) -> list[Violation]`; `Violation(quadrant, path, file_class, proposed_target)`; `FileClass.PAYLOAD`.
- Produces: `Quadrant.TRACKED_PAYLOAD` (value `"tracked_payload"`), emitted for `class=PAYLOAD, loc=DATA, git_tracked=True` with `proposed_target=None`. `_planned_action` already returns `"flag"` for any non-`STRANDED_RECORD` quadrant, so `render_json` surfaces it as action `"flag"`.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_data_audit.py`:

```python
def test_tracked_payload_inside_data_flagged(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/big.feather", b"\x00" * 32)  # PAYLOAD by ext
    # Untracked payload under data/ → no violation (the normal, healthy case).
    assert not [v for v in audit_project(tmp_path)
                if v.quadrant is Quadrant.TRACKED_PAYLOAD]
    # Track it → TRACKED_PAYLOAD violation, report-only (no move target).
    subprocess.run(["git", "add", "-f", "data/processed/exp1/big.feather"],
                   cwd=tmp_path, check=True)
    tracked = [v for v in audit_project(tmp_path)
               if v.quadrant is Quadrant.TRACKED_PAYLOAD]
    assert len(tracked) == 1
    assert tracked[0].path == "data/processed/exp1/big.feather"
    assert tracked[0].proposed_target is None
    # Stable JSON contract surfaces it as a report-only "flag" action.
    payload = json.loads(render_json(tracked))
    assert payload["violations"][0]["quadrant"] == "tracked_payload"
    assert payload["violations"][0]["action"] == "flag"
    assert payload["violations"][0]["performed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_audit.py::test_tracked_payload_inside_data_flagged -v`
Expected: FAIL with `AttributeError: TRACKED_PAYLOAD` (enum member missing).

- [ ] **Step 3: Add the enum member**

In `science/src/science_tool/data_audit.py`, extend `Quadrant`:

```python
class Quadrant(StrEnum):
    STRANDED_RECORD = "stranded_record"
    LEAKED_PAYLOAD = "leaked_payload"
    TRACKED_PAYLOAD = "tracked_payload"
    FLAG = "flag"
```

- [ ] **Step 4: Add the detection branch**

In `_violation_for`, add the branch immediately after the existing `LEAKED_PAYLOAD` branch (before the `FLAG` branch):

```python
    if cls is FileClass.PAYLOAD and is_tracked and loc == "DATA":
        # Tracked payload sitting in ignored data/ territory. Remediation is
        # `git rm --cached` (untrack-in-place); never an auto-move, so no target.
        return Violation(Quadrant.TRACKED_PAYLOAD, rel.as_posix(), cls, None)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_data_audit.py::test_tracked_payload_inside_data_flagged -v`
Expected: PASS.

- [ ] **Step 6: Run the full data-audit suite (no regressions)**

Run: `pytest tests/test_data_audit.py tests/test_data_audit_fix.py tests/test_data_audit_cli.py -q`
Expected: all pass (existing quadrants/fixer untouched).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/data_audit.py science/tests/test_data_audit.py
git commit -m "feat(data-audit): add TRACKED_PAYLOAD quadrant for tracked payloads under data/"
```

---

### Task 2: Shared `project_package/core.py` + labnote refactor (golden-protected)

Extract the hashing/versioning primitives; refactor labnote to consume them with **byte-identical** output.

**Files:**
- Create: `science/src/science_tool/project_package/__init__.py`
- Create: `science/src/science_tool/project_package/core.py`
- Create: `science/tests/test_project_package_core.py`
- Modify: `science/src/science_tool/labnote_export.py` (`_sha256` L179-180, `_json_resource` L183-193, `_data_version` L471-486)
- Test (existing, must stay green): `science/tests/test_labnote_export.py`

**Interfaces:**
- Produces:
  - `FileResource` — frozen dataclass with `path: str`, `sha256: str`, `bytes: int`.
  - `file_resource(root: Path, relpath: str) -> FileResource` — hashes `root / relpath`, `path` field = `relpath` verbatim.
  - `content_version(base: str, chunks: Iterable[bytes]) -> str` — returns `f"{base}+{<sha256 of concatenated chunks>[:12]}"`, folding chunks in order with NO separators.
- Consumed by: Task 3+ (serialize) and the refactored labnote.

- [ ] **Step 1: Write the failing core unit test**

Create `science/tests/test_project_package_core.py`:

```python
import hashlib
from pathlib import Path

from science_tool.project_package.core import (
    FileResource,
    content_version,
    file_resource,
)


def test_file_resource_hashes_and_sizes(tmp_path: Path):
    (tmp_path / "a.txt").write_bytes(b"hello")
    fr = file_resource(tmp_path, "a.txt")
    assert fr == FileResource(
        path="a.txt",
        sha256=hashlib.sha256(b"hello").hexdigest(),
        bytes=5,
    )


def test_content_version_is_separator_free_concat():
    expected = hashlib.sha256(b"ab" + b"cd").hexdigest()[:12]
    assert content_version("2026-06-29", [b"ab", b"cd"]) == f"2026-06-29+{expected}"


def test_content_version_ignores_chunk_boundaries():
    v1 = content_version("0", [b"a", b"bc"])
    v2 = content_version("0", [b"ab", b"c"])
    # No length prefixes/separators: different chunking, same concatenation → same digest.
    assert v1 == v2
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_project_package_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.project_package'`.

- [ ] **Step 3: Create the package and core module**

Create `science/src/science_tool/project_package/__init__.py`:

```python
"""Project-package primitives shared by labnote export and project serialize."""
```

Create `science/src/science_tool/project_package/core.py`:

```python
"""Hashing and versioning primitives shared across project-package profiles.

Zero app/entity coupling — these operate on files and byte streams only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileResource:
    path: str       # archive-relative posix path (no top-level project dir)
    sha256: str
    bytes: int


def file_resource(root: Path, relpath: str) -> FileResource:
    """Hash one file under ``root``; ``path`` is ``relpath`` verbatim."""
    data = (root / relpath).read_bytes()
    return FileResource(
        path=relpath,
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
    )


def content_version(base: str, chunks: Iterable[bytes]) -> str:
    """Deterministic version string ``f"{base}+{digest12}"``.

    Folds sha256 over ``chunks`` in order with NO separators or length
    prefixes, so existing call sites that build their own byte stream keep
    their digest byte-for-byte.
    """
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return f"{base}+{digest.hexdigest()[:12]}"
```

- [ ] **Step 4: Run the core test to verify it passes**

Run: `pytest tests/test_project_package_core.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Pin the labnote `data_version` golden BEFORE refactor**

The existing labnote suite pins only the `data_version` base prefix (`2026-06-28+…`) and
change-sensitivity — **not** the exact digest. Add a golden that pins the full digest, so the
Task 2 byte-stream refactor is proven byte-identical. The literal below was computed from the
current (pre-refactor) code against the `write_minimal_project` fixture. Add to
`science/tests/test_labnote_export.py`:

```python
def test_data_version_is_stable_golden(tmp_path: Path):
    write_minimal_project(tmp_path)
    out = tmp_path / "out"
    export_labnote_package(project_root=tmp_path, out_dir=out)
    project = json.loads((out / "project.json").read_text())
    # Golden: exact digest must survive the project_package.core extraction byte-for-byte.
    assert project["package"]["data_version"] == "2026-06-28+4d829889ef73"
```

Confirm it passes against the **pre-refactor** code first (this proves the literal is correct
before any refactor exists to break it):

Run: `pytest tests/test_labnote_export.py::test_data_version_is_stable_golden -v`
Expected: PASS.

> If this fails at authoring time, the fixture has changed since the plan was written —
> recompute by printing `project["package"]["data_version"]` and use that literal; do **not**
> change the value after the Task 2 refactor (that would defeat the golden).

- [ ] **Step 6: Refactor labnote to consume the core (keep output identical)**

In `science/src/science_tool/labnote_export.py`, add the import near the other `science_tool` imports:

```python
from science_tool.project_package.core import content_version, file_resource
```

Replace `_sha256` (L179-180) and `_json_resource` (L183-193) with a single `_json_resource` built on `file_resource` (drop `_sha256` — it has no other caller):

```python
def _json_resource(name: str, path: str, kind: str, root: Path) -> dict[str, Any]:
    fr = file_resource(root, path)
    return {
        "name": name,
        "path": path,
        "kind": kind,
        "sensitivity": "public",
        "bytes": fr.bytes,
        "sha256": fr.sha256,
        "media_type": "application/json",
    }
```

Replace `_data_version` (L471-486) so it delegates to `content_version` while yielding the **exact same byte sequence** it hashes today:

```python
def _data_version(project_root: Path, raw_config: dict[str, Any], entities: list[ExportedEntity]) -> str:
    base = str(raw_config.get("last_modified") or raw_config.get("version") or "0")

    def chunks() -> "Iterator[bytes]":
        yield (project_root / "science.yaml").read_bytes()
        bib = project_root / "papers" / "references.bib"
        if bib.exists():
            yield bib.read_bytes()
        graph = project_root / "knowledge" / "graph.trig"
        if graph.exists():
            yield graph.read_bytes()
        for entity in entities:
            yield entity.source_path.encode("utf-8")
            yield json.dumps(entity.frontmatter, sort_keys=True, default=str).encode("utf-8")
            yield json.dumps(entity.record, sort_keys=True, default=str).encode("utf-8")
            yield entity.markdown.encode("utf-8")

    return content_version(base, chunks())
```

Add `Iterator` to the `typing` import at the top of the file if not already present (`from typing import Any, Iterator`). Then **remove the now-unused `import hashlib`** (line 3) — after this refactor labnote's only two `hashlib` uses (old `_sha256` and `_data_version`) are gone; ruff would otherwise flag the dead import.

- [ ] **Step 7: Run the golden + full labnote suite (byte-identical proof)**

Run: `pytest tests/test_labnote_export.py -v`
Expected: ALL pass, including `test_data_version_is_stable_golden` (digest unchanged) — this is the behavior-neutral proof.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/project_package/ science/tests/test_project_package_core.py \
        science/src/science_tool/labnote_export.py science/tests/test_labnote_export.py
git commit -m "refactor(labnote): extract file_resource/content_version into project_package.core"
```

---

### Task 3: Serialize selection + payload inventory + manifest (pure logic)

Build the file-level selection, the payload hash inventory (with cycle/non-regular guards), and the manifest assembly — no archiving yet.

**Files:**
- Create: `science/src/science_tool/project_package/serialize.py`
- Test: `science/tests/test_project_serialize.py`

**Interfaces:**
- Produces:
  - `class SerializeError(Exception)`.
  - `SerializeResult` — frozen dataclass `out_path: Path`, `file_count: int`, `payload_count: int`, `forced: bool`.
  - `_tracked_files(project_root: Path) -> list[str]` — `git ls-files -z`; **raises `SerializeError`** if not a git worktree.
  - `_selected_source(tracked: list[str]) -> list[str]` — sorted unique tracked paths under `entities/`/`results/` plus tracked top-level singles.
  - `_payload_inventory(project_root: Path, data_dirs, tracked_set: set[str]) -> list[dict]` — sorted `{path, sha256, bytes, git_tracked}` over `DEFAULT_DATA_DIRS`; raises `SerializeError` on symlink cycle / non-regular entry.
  - `_build_manifest(project_root, files: list[FileResource], payloads: list[dict], *, audit_passed: bool, forced: bool, git_commit: str) -> dict`. The commit is resolved — and hard-failed when absent — in Task 5, then passed in; `_build_manifest` stays git-free and unit-testable.
- Consumes: `FileResource`, `file_resource`, `content_version` from `project_package.core`; `DEFAULT_DATA_DIRS` from `data_worktree`; `load_project_config` from `project_config`.

- [ ] **Step 1: Write failing tests for selection + inventory + manifest**

Create `science/tests/test_project_serialize.py`:

```python
import json
import subprocess
from pathlib import Path

import pytest

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_package.serialize import (
    SerializeError,
    _build_manifest,
    _payload_inventory,
    _selected_source,
    _tracked_files,
)


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes = b"x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _commit_all(root: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def test_tracked_files_raises_without_git(tmp_path: Path):
    with pytest.raises(SerializeError):
        _tracked_files(tmp_path)


def test_selected_source_filters_to_roots_and_singles():
    tracked = [
        "science.yaml",
        "papers/references.bib",
        "knowledge/graph.trig",
        "entities/questions/q1.md",
        "results/exp/summary.md",
        "doc/notes.md",          # excluded: not a source root / single
        "data/processed/x.csv",  # excluded: data/
        "README.md",             # excluded: untracked-root single not in allowlist
    ]
    assert _selected_source(tracked) == [
        "entities/questions/q1.md",
        "knowledge/graph.trig",
        "papers/references.bib",
        "results/exp/summary.md",
        "science.yaml",
    ]


def test_payload_inventory_hashes_data_without_copy(tmp_path: Path):
    import hashlib
    _write(tmp_path, "data/processed/a.parquet", b"\x01\x02\x03")
    inv = _payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())
    assert inv == [{
        "path": "data/processed/a.parquet",
        "sha256": hashlib.sha256(b"\x01\x02\x03").hexdigest(),
        "bytes": 3,
        "git_tracked": False,
    }]


def test_payload_inventory_marks_tracked(tmp_path: Path):
    _write(tmp_path, "data/raw/t.bin", b"\x00")
    inv = _payload_inventory(
        tmp_path, DEFAULT_DATA_DIRS, tracked_set={"data/raw/t.bin"}
    )
    assert inv[0]["git_tracked"] is True


def test_payload_inventory_guards_symlink_cycle(tmp_path: Path):
    d = tmp_path / "data" / "processed"
    d.mkdir(parents=True)
    (d / "loop").symlink_to(tmp_path / "data" / "processed", target_is_directory=True)
    with pytest.raises(SerializeError):
        _payload_inventory(tmp_path, DEFAULT_DATA_DIRS, tracked_set=set())


def test_build_manifest_shape(tmp_path: Path):
    from science_tool.project_package.core import file_resource
    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    files = [file_resource(tmp_path, "science.yaml")]
    payloads = [{"path": "data/raw/a", "sha256": "ab", "bytes": 1, "git_tracked": False}]
    manifest = _build_manifest(
        tmp_path, files, payloads, audit_passed=True, forced=False, git_commit="abc123"
    )
    assert manifest["schema_version"] == "science-project-serialized.v1"
    assert manifest["project"]["id"] == "demo"
    assert manifest["project"]["label"] == "Demo"
    assert manifest["boundary_audit"] == {"passed": True, "forced": False}
    assert manifest["files"][0]["path"] == "science.yaml"
    assert manifest["payloads"] == payloads
    assert manifest["data_version"].startswith("2026-06-29+")


def test_data_version_changes_on_path_rename(tmp_path: Path):
    # Canonical-record hashing: identical bytes at a different path must change
    # the version (the manifest changed, so the version must too).
    from science_tool.project_package.core import FileResource

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    a = [FileResource(path="entities/a.md", sha256="deadbeef", bytes=4)]
    b = [FileResource(path="entities/b.md", sha256="deadbeef", bytes=4)]
    va = _build_manifest(
        tmp_path, a, [], audit_passed=True, forced=False, git_commit="abc123"
    )["data_version"]
    vb = _build_manifest(
        tmp_path, b, [], audit_passed=True, forced=False, git_commit="abc123"
    )["data_version"]
    assert va != vb
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_project_serialize.py -v`
Expected: FAIL with `ModuleNotFoundError` / missing `serialize` symbols.

- [ ] **Step 3: Implement selection, inventory, and manifest**

Create `science/src/science_tool/project_package/serialize.py`:

```python
"""`science project serialize` — deterministic, git-faithful project bundle.

Source files (entities + results, no data/ payloads) + a manifest that
hash-inventories the excluded payloads. See
docs/plans/2026-06-29-project-serialize-design.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_config import load_project_config
from science_tool.project_package.core import FileResource, content_version, file_resource

SCHEMA_VERSION = "science-project-serialized.v1"
SOURCE_ROOTS = ("entities", "results")
TOP_LEVEL_SINGLES = ("science.yaml", "papers/references.bib", "knowledge/graph.trig")


class SerializeError(Exception):
    """Raised for any hard-fail precondition or guard failure."""


@dataclass(frozen=True)
class SerializeResult:
    out_path: Path
    file_count: int
    payload_count: int
    forced: bool


def _tracked_files(project_root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SerializeError(
            f"not a git worktree (git ls-files failed): {project_root}"
        ) from exc
    return [p for p in out.decode("utf-8").split("\0") if p]


def _selected_source(tracked: list[str]) -> list[str]:
    selected: set[str] = set()
    for rel in tracked:
        if rel in TOP_LEVEL_SINGLES or rel.split("/", 1)[0] in SOURCE_ROOTS:
            selected.add(rel)
    return sorted(selected)


def _payload_inventory(
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
        raise SerializeError(f"symlink cycle under data dir: {directory}")
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
            raise SerializeError(f"non-regular file under data dir: {entry.path}")


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

    chunks: list[bytes] = []
    for fr in files:
        chunks.append(json.dumps(
            {"path": fr.path, "sha256": fr.sha256, "bytes": fr.bytes}, sort_keys=True
        ).encode("utf-8"))
    for p in payloads:
        chunks.append(json.dumps(
            {"path": p["path"], "sha256": p["sha256"], "bytes": p["bytes"],
             "git_tracked": p["git_tracked"]},
            sort_keys=True,
        ).encode("utf-8"))

    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": config.id,
            "label": str(raw.get("name") or config.id),
            "summary": raw.get("summary"),
        },
        "data_version": content_version(base, chunks),
        "provenance": {"git_commit": git_commit, "tool": "science"},
        "boundary_audit": {"passed": audit_passed, "forced": forced},
        "files": [{"path": fr.path, "sha256": fr.sha256, "bytes": fr.bytes} for fr in files],
        "payloads": payloads,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_project_serialize.py -v`
Expected: PASS (selection, inventory ×3, manifest).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_package/serialize.py science/tests/test_project_serialize.py
git commit -m "feat(serialize): file selection, payload hash inventory, manifest assembly"
```

---

### Task 4: Deterministic archive writer

Write the source files + manifest into a byte-reproducible `.tar.gz`.

**Files:**
- Modify: `science/src/science_tool/project_package/serialize.py`
- Test: `science/tests/test_project_serialize.py`

**Interfaces:**
- Produces: `_write_archive(out_path: Path, project_root: Path, project_id: str, files: list[FileResource], manifest: dict) -> None` — writes a gzip(`mtime=0`) tar with members `<project_id>/manifest.json` + `<project_id>/<file.path>`, sorted by arcname, each normalized (`mtime=0`, `uid=gid=0`, `uname=gname=""`, mode `0o644`, `REGTYPE`). No directory entries.

- [ ] **Step 1: Write the failing determinism test**

Append to `science/tests/test_project_serialize.py`:

```python
def test_write_archive_is_deterministic(tmp_path: Path):
    import tarfile
    from science_tool.project_package.core import file_resource
    from science_tool.project_package.serialize import _build_manifest, _write_archive

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    files = [file_resource(tmp_path, "science.yaml"),
             file_resource(tmp_path, "entities/questions/q1.md")]
    manifest = _build_manifest(
        tmp_path, files, [], audit_passed=True, forced=False, git_commit="abc123"
    )

    a = tmp_path / "a.tar.gz"
    b = tmp_path / "b.tar.gz"
    _write_archive(a, tmp_path, "demo", files, manifest)
    _write_archive(b, tmp_path, "demo", files, manifest)
    assert a.read_bytes() == b.read_bytes()  # byte-identical

    with tarfile.open(a, "r:gz") as tar:
        names = tar.getnames()
        assert names == sorted(names)  # sorted members
        assert "demo/manifest.json" in names
        assert "demo/entities/questions/q1.md" in names
        for m in tar.getmembers():
            assert m.mtime == 0 and m.uid == 0 and m.gid == 0
            assert m.uname == "" and m.gname == "" and m.mode == 0o644
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_project_serialize.py::test_write_archive_is_deterministic -v`
Expected: FAIL with `ImportError: cannot import name '_write_archive'`.

- [ ] **Step 3: Implement the writer**

Add to `science/src/science_tool/project_package/serialize.py` (imports `io`, `gzip`, `tarfile` at top — add `import gzip`, `import io`, `import tarfile`):

```python
def _write_archive(
    out_path: Path,
    project_root: Path,
    project_id: str,
    files: list[FileResource],
    manifest: dict,
) -> None:
    members: list[tuple[str, bytes]] = [(
        f"{project_id}/manifest.json",
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )]
    for fr in files:
        members.append((f"{project_id}/{fr.path}", (project_root / fr.path).read_bytes()))
    members.sort(key=lambda m: m[0])

    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for arcname, data in members:
                info = tarfile.TarInfo(arcname)
                info.size = len(data)
                info.mtime = 0
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.type = tarfile.REGTYPE
                tar.addfile(info, io.BytesIO(data))
    out_path.write_bytes(raw.getvalue())
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_project_serialize.py::test_write_archive_is_deterministic -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_package/serialize.py science/tests/test_project_serialize.py
git commit -m "feat(serialize): deterministic tar.gz writer"
```

---

### Task 5: `serialize_project` orchestration (preconditions, gate, force, out-guard)

Tie selection → inventory → manifest → archive behind all the precondition and boundary checks.

**Files:**
- Modify: `science/src/science_tool/project_package/serialize.py`
- Test: `science/tests/test_project_serialize.py`

**Interfaces:**
- Produces: `serialize_project(project_root: Path, out_archive: Path, *, force: bool = False) -> SerializeResult`; helpers `_head_commit`, `_assert_clean_source`, `_assert_regular_source`, `_assert_safe_project_id`.
- Consumes: `audit_project` from `data_audit`; `resolve_data_policy` + `load_project_config` from `project_config`.
- Order of hard-fails (only the boundary gate is bypassable by `force`): (1) `--out` inside project root; (2) `science.yaml` exists; (3) git worktree (`_tracked_files`) + `science.yaml` tracked; (4) **HEAD commit exists**; (5) select source; (6) **regular-file source** (no symlinks); (7) **clean source vs HEAD**; (8) load config/policy with errors wrapped as `SerializeError`; (9) boundary gate; (10) read source + payloads, wrapping `OSError`→`SerializeError`; (11) build manifest with config/manifest errors wrapped; (12) **safe project id**; (13) write archive, wrapping `OSError`.

- [ ] **Step 1: Write the failing orchestration tests**

Append to `science/tests/test_project_serialize.py`:

```python
def test_serialize_happy_path(tmp_path: Path):
    import tarfile
    from science_tool.project_package.serialize import serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\nlast_modified: 2026-06-29\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _write(tmp_path, "results/exp/summary.md", b"# s\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    # Untracked payload (the healthy case): inventoried by hash, never copied,
    # not a TRACKED_PAYLOAD violation.
    _write(tmp_path, "data/processed/big.parquet", b"\x09" * 16)

    out = tmp_path.parent / "bundle.tar.gz"
    result = serialize_project(tmp_path, out, force=False)
    assert result.out_path == out and out.exists()
    assert result.forced is False

    with tarfile.open(out, "r:gz") as tar:
        names = set(tar.getnames())
        manifest = json.loads(tar.extractfile("demo/manifest.json").read())
    assert "demo/entities/questions/q1.md" in names
    assert "demo/results/exp/summary.md" in names
    assert "demo/science.yaml" in names
    # data/ never copied:
    assert not any(n.startswith("demo/data/") for n in names)
    # but inventoried by hash:
    assert manifest["payloads"][0]["path"] == "data/processed/big.parquet"
    assert manifest["payloads"][0]["git_tracked"] is False
    assert all(f["path"] != "data/processed/big.parquet" for f in manifest["files"])
    assert manifest["boundary_audit"] == {"passed": True, "forced": False}


def test_serialize_omits_untracked_results(tmp_path: Path):
    import tarfile
    from science_tool.project_package.serialize import serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "results/exp/tracked.md", b"# t\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    _write(tmp_path, "results/exp/untracked.md", b"# u\n")  # never committed

    out = tmp_path.parent / "b2.tar.gz"
    serialize_project(tmp_path, out)
    with tarfile.open(out, "r:gz") as tar:
        names = set(tar.getnames())
    assert "demo/results/exp/tracked.md" in names
    assert "demo/results/exp/untracked.md" not in names


def test_serialize_refuses_on_boundary_violation(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    # A stranded record under data/ is a boundary violation.
    _write(tmp_path, "data/processed/exp/RESULTS.md", b"# results\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)

    out = tmp_path.parent / "b3.tar.gz"
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, out, force=False)
    assert not out.exists()

    # --force builds and records forced=true.
    result = serialize_project(tmp_path, out, force=True)
    assert result.forced is True and out.exists()


def test_serialize_rejects_out_inside_root(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path / "results" / "bundle.tar.gz")


def test_serialize_requires_tracked_science_yaml(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "entities/questions/q1.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=tmp_path, check=True)  # yaml untracked
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path.parent / "b4.tar.gz")


def test_serialize_refuses_dirty_source(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    (tmp_path / "entities" / "questions" / "q1.md").write_bytes(b"# q changed\n")  # dirty vs HEAD
    out = tmp_path.parent / "dirty.tar.gz"
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, out)
    assert not out.exists()


def test_serialize_reports_dirty_source_before_invalid_config(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    # The dirty science.yaml is now invalid YAML, but source drift should be
    # reported first because the package promises reproducibility from HEAD.
    (tmp_path / "science.yaml").write_text("id: [unterminated\n", encoding="utf-8")
    with pytest.raises(SerializeError, match="differ from HEAD"):
        serialize_project(tmp_path, tmp_path.parent / "dirty-config.tar.gz")


def test_serialize_rejects_symlink_source(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/real.md", b"# real\n")
    (tmp_path / "entities" / "questions" / "link.md").symlink_to(
        tmp_path / "entities" / "questions" / "real.md"
    )
    _init_repo(tmp_path)
    _commit_all(tmp_path)  # git tracks the symlink as a symlink
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path.parent / "sym.tar.gz")


def test_serialize_requires_head_commit(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "science.yaml"], cwd=tmp_path, check=True)  # staged, never committed
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, tmp_path.parent / "nohead.tar.gz")


def test_serialize_rejects_unsafe_project_id(tmp_path: Path):
    from science_tool.project_package.serialize import SerializeError, serialize_project

    _write(tmp_path, "science.yaml", b"id: bad/id\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    out = tmp_path.parent / "bad.tar.gz"
    with pytest.raises(SerializeError):
        serialize_project(tmp_path, out)
    assert not out.exists()


def test_serialize_wraps_oserror_on_unreadable_payload(tmp_path: Path):
    import os
    import stat

    from science_tool.project_package.serialize import SerializeError, serialize_project

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses file permissions")
    _write(tmp_path, "science.yaml", b"id: demo\nname: Demo\n")
    _write(tmp_path, "entities/questions/q1.md", b"# q\n")
    _init_repo(tmp_path)
    _commit_all(tmp_path)
    payload = _write(tmp_path, "data/processed/secret.bin", b"\x00")  # untracked payload
    payload.chmod(0)
    try:
        with pytest.raises(SerializeError):
            serialize_project(tmp_path, tmp_path.parent / "oserr.tar.gz")
    finally:
        payload.chmod(stat.S_IRUSR | stat.S_IWUSR)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_project_serialize.py -k serialize -v`
Expected: FAIL with `ImportError: cannot import name 'serialize_project'`.

- [ ] **Step 3: Implement the orchestration**

Add to `science/src/science_tool/project_package/serialize.py` the imports near the top
(`import re` with the other stdlib imports):

```python
import re

from pydantic import ValidationError

from science_tool.data_audit import audit_project
from science_tool.project_config import resolve_data_policy
```

And the helpers + function:

```python
_SAFE_ID_RE = re.compile(r"\A[A-Za-z0-9._-]+\Z")


def _out_inside_root(project_root: Path, out_archive: Path) -> bool:
    root = project_root.resolve()
    out_abs = out_archive.parent.resolve() / out_archive.name
    return root == out_abs or root in out_abs.parents


def _head_commit(project_root: Path) -> str:
    """HEAD sha; hard-fail if the repo has no commit (reproducibility anchor)."""
    try:
        return subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SerializeError(
            "repository has no HEAD commit; nothing committed to serialize from"
        ) from exc


def _assert_regular_source(project_root: Path, source_rels: list[str]) -> None:
    for rel in source_rels:
        p = project_root / rel
        if p.is_symlink():
            raise SerializeError(f"selected source is a symlink (not git-faithful): {rel}")
        if not p.is_file():
            raise SerializeError(f"selected source is not a regular file: {rel}")


def _assert_clean_source(project_root: Path) -> None:
    """Every selected source path must match HEAD, so git_commit truly reproduces it."""
    pathspecs = [*SOURCE_ROOTS, *TOP_LEVEL_SINGLES]
    result = subprocess.run(
        ["git", "-C", str(project_root), "diff", "--name-only", "HEAD", "--", *pathspecs],
        capture_output=True, text=True, check=True,
    )
    dirty = [p for p in result.stdout.splitlines() if p]
    if dirty:
        raise SerializeError(
            f"refusing to serialize: {len(dirty)} selected source file(s) differ from HEAD "
            f"(e.g. {dirty[0]}). Commit or stash before serializing."
        )


def _assert_safe_project_id(project_id: str) -> None:
    if project_id in ("", ".", "..") or "/" in project_id or "\\" in project_id \
            or not _SAFE_ID_RE.match(project_id):
        raise SerializeError(f"unsafe project id for archive path: {project_id!r}")


def _config_error(exc: Exception) -> SerializeError:
    return SerializeError(f"invalid or unreadable science.yaml: {exc}")


def serialize_project(
    project_root: Path,
    out_archive: Path,
    *,
    force: bool = False,
) -> SerializeResult:
    project_root = project_root.expanduser().resolve()
    out_archive = out_archive.expanduser()

    if _out_inside_root(project_root, out_archive):
        raise SerializeError(f"--out must not be inside the project root: {out_archive}")
    if not (project_root / "science.yaml").exists():
        raise SerializeError(f"missing science.yaml: {project_root / 'science.yaml'}")

    tracked = _tracked_files(project_root)  # raises if not a git worktree
    if "science.yaml" not in tracked:
        raise SerializeError("science.yaml is not git-tracked; cannot build a portable bundle")
    commit = _head_commit(project_root)  # raises if no HEAD commit

    source_rels = _selected_source(tracked)
    _assert_regular_source(project_root, source_rels)
    _assert_clean_source(project_root)

    try:
        policy = resolve_data_policy(load_project_config(project_root))
    except (OSError, ValueError, yaml.YAMLError, ValidationError) as exc:
        raise _config_error(exc) from exc

    violations = audit_project(project_root, policy)
    if violations and not force:
        quadrants = sorted({v.quadrant.value for v in violations})
        raise SerializeError(
            f"refusing to serialize: {len(violations)} data-audit violation(s) "
            f"[{', '.join(quadrants)}]. Run `science data audit` to inspect, or pass --force."
        )
    forced = bool(violations) and force

    try:
        files = [file_resource(project_root, rel) for rel in source_rels]
        payloads = _payload_inventory(project_root, DEFAULT_DATA_DIRS, set(tracked))
    except OSError as exc:
        raise SerializeError(f"filesystem error reading project source: {exc}") from exc

    try:
        manifest = _build_manifest(
            project_root, files, payloads,
            audit_passed=not violations, forced=forced, git_commit=commit,
        )
    except (OSError, ValueError, yaml.YAMLError, ValidationError) as exc:
        raise _config_error(exc) from exc

    _assert_safe_project_id(manifest["project"]["id"])

    try:
        out_archive.parent.mkdir(parents=True, exist_ok=True)
        _write_archive(out_archive, project_root, manifest["project"]["id"], files, manifest)
    except OSError as exc:
        raise SerializeError(f"filesystem error writing archive: {exc}") from exc
    return SerializeResult(out_archive, len(files), len(payloads), forced)
```

Note: `_payload_inventory` raises `SerializeError` for its own cycle/non-regular guards; those
pass through the `except OSError` (they are not `OSError`). Only genuine read/stat failures are
wrapped.

- [ ] **Step 4: Run the serialize tests**

Run: `pytest tests/test_project_serialize.py -v`
Expected: ALL pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_package/serialize.py science/tests/test_project_serialize.py
git commit -m "feat(serialize): serialize_project orchestration with boundary gate and guards"
```

---

### Task 6: CLI wiring — `science project serialize`

Expose `serialize_project` under the existing `project` group.

**Files:**
- Modify: `science/src/science_tool/cli.py` (the `@main.group() def project()` block at ~L4572, after `project.add_command(_artifacts_group)`)
- Test: `science/tests/test_project_serialize_cli.py`

**Interfaces:**
- Consumes: `serialize_project`, `SerializeError`, `SerializeResult` from `project_package.serialize`.
- Produces: `project serialize --project-root <root> --out <file.tar.gz> [--force]`; exit 0 success, exit 1 (via `click.ClickException`) on any `SerializeError`.

- [ ] **Step 1: Write the failing CLI test**

Create `science/tests/test_project_serialize_cli.py`:

```python
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _project(root: Path) -> None:
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (root / "entities" / "questions" / "q1.md").write_text("# q\n", encoding="utf-8")
    _init_repo(root)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, check=True)


def test_cli_serialize_success(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _project(proj)
    out = tmp_path / "bundle.tar.gz"
    result = CliRunner().invoke(
        main, ["project", "serialize", "--project-root", str(proj), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "Serialized" in result.output


def test_cli_serialize_refuses_violation_exit_1(tmp_path: Path):
    proj = tmp_path / "proj"
    (proj / "data" / "processed" / "exp").mkdir(parents=True)
    (proj / "science.yaml").write_text("id: demo\nname: Demo\n", encoding="utf-8")
    (proj / "data" / "processed" / "exp" / "RESULTS.md").write_text("# r\n", encoding="utf-8")
    _init_repo(proj)
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=proj, check=True)
    out = tmp_path / "b.tar.gz"
    result = CliRunner().invoke(
        main, ["project", "serialize", "--project-root", str(proj), "--out", str(out)]
    )
    assert result.exit_code == 1
    assert not out.exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_project_serialize_cli.py -v`
Expected: FAIL (no `serialize` subcommand → click usage error, exit 2).

- [ ] **Step 3: Add the command**

In `science/src/science_tool/cli.py`, immediately after `project.add_command(_artifacts_group)`:

```python
@project.command("serialize")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root containing science.yaml.",
)
@click.option(
    "--out",
    "out_archive",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Output .tar.gz path (must be outside the project root).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Build despite data-audit boundary violations (audit only; "
    "never bypasses missing/untracked science.yaml or guard failures).",
)
def project_serialize(project_root: Path, out_archive: Path, force: bool) -> None:
    """Serialize the tracked project source into a deterministic, shareable bundle.

    Reproducibility, not a privacy scrubber: ships all git-tracked entities and
    results faithfully; restricted material must not be tracked.
    """
    from science_tool.project_package.serialize import SerializeError, serialize_project

    try:
        result = serialize_project(project_root, out_archive, force=force)
    except SerializeError as exc:
        raise click.ClickException(str(exc)) from exc
    suffix = " [forced]" if result.forced else ""
    click.echo(
        f"Serialized {result.file_count} file(s), {result.payload_count} payload(s)"
        f"{suffix} → {result.out_path}"
    )
```

- [ ] **Step 4: Run the CLI test**

Run: `pytest tests/test_project_serialize_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke-test registration**

Run: `python -c "from science_tool.cli import main; print('serialize' in main.commands['project'].commands)"`
Expected: `True`.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_project_serialize_cli.py
git commit -m "feat(serialize): wire science project serialize CLI command"
```

---

## Final verification (after all tasks)

- [ ] Run the full touched-surface suite:

Run: `pytest tests/test_data_audit.py tests/test_labnote_export.py tests/test_project_package_core.py tests/test_project_serialize.py tests/test_project_serialize_cli.py -q`
Expected: all green.

- [ ] Lint the new/changed files:

Run: `ruff check src/science_tool/project_package/ src/science_tool/data_audit.py src/science_tool/labnote_export.py src/science_tool/cli.py`
Expected: clean.

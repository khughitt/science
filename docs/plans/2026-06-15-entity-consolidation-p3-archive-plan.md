# Entity Consolidation P3 — Archive Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** relocate hidden-status entities into a tracked, scan-excluded `entities/_archive/` tree recorded in an append-only index, keeping their IDs resolvable (validate + graph) without ever rehydrating archived markdown as live entities.

**Architecture:** A single stdlib-only scanner (`entity_scan.py`) becomes the sole recursive `entities/` reader and skips `_archive/`; an append-only `archive-index.jsonl` (fold-to-active, tombstone reversal) is the source of truth for archived-id resolution; status-driven `archive`/`unarchive` mutators relocate (move-first-then-append) and restore; validate + graph build resolve archived refs from the index (graph emits a tombstone stub node), never loading archived files.

**Tech Stack:** Python 3.13, pydantic v2, Click CLI, pytest, rdflib (graph), PyYAML. Design spec: `docs/plans/2026-06-15-entity-consolidation-p3-archive-design.md`.

**Test command (worktree has NO `.venv` — use the main repo venv with `PYTHONPATH=src` from the worktree `science/` dir, all `rtk`-prefixed):**
```
cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest <path> -v
```

**Scope notes (deviations from the spec, flagged per writing-plans):**
- `--include-archived` is implemented on `science entities list` (index-merge, archive-origin tagged) in P3. **Big-picture bundle `--include-archived` deep-read is deferred to P4**, where archived members become relevant via digests (YAGNI — nothing in P3 needs archived bodies in bundles). The `iter_entity_markdown(include_archived=True)` capability is still built and unit-tested.
- Graph archive-aware resolution + stub node covers the **three acceptance edge types** the spec names — `related:`, `source_refs:`, `relations[].target`. The remaining kind-specific edge predicates (participants/propositions/discusses/…) rarely reference superseded entities; routing them is a documented additive follow-up, not a P3 gate.

---

## File structure

**New files:**
- `science/src/science_tool/entity_scan.py` — the sole recursive `entities/` scanner.
- `science/src/science_tool/archive.py` — index models + I/O, relocate/restore, report-then-apply mutators, `verify_archive`, resolution feed.
- Tests: `test_entity_scan.py`, `test_resolve_local_home_reserved.py`, `test_entity_scan_guard.py`, `test_archive_index.py`, `test_archive_mutators.py`, `test_archive_verify.py`, `test_archive_resolution_validate.py`, `test_archive_resolution_graph.py`, `test_archive_cli.py`, `test_search_cli.py`, `test_list_include_archived.py`, `test_archive_acceptance.py`.

**Modified files:**
- `entities.py` — `_resolve_local_home` guard; route `_load_markdown_entities`; `list_entities(include_archived=...)`.
- `consolidation.py` — route `iter_entity_frontmatter`.
- `graph/storage_adapters/markdown.py` — route `discover` (always `include_archived=False`).
- `validate/checks/cross_references.py` — route scan; union archive resolvable ids; archive-verify subcheck.
- `validate/checks/id_prefixes.py`, `entity_conformance.py`, `hypotheses.py` — route the recursive `entities/` scans.
- `big_picture/validator.py` — route `_collect_project_ids`.
- `entities_inventory.py` — add `_archive` to `_latest_activity` skip-set.
- `graph/materialize.py` — archive-aware edge resolution + stub node (3 edge types).
- `cli.py` — `entities archive` / `entities unarchive`; new top-level `search`.
- `.rgignore` (repo root) — ergonomic `entities/_archive/` entry.

---

### Task 1: `entity_scan.py` — the shared recursive scanner

**Files:**
- Create: `science/src/science_tool/entity_scan.py`
- Test: `science/tests/test_entity_scan.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_entity_scan.py
"""Tests for the sole sanctioned recursive entities/ scanner (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.entity_scan import iter_entity_markdown


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nid: x\n---\n", encoding="utf-8")


def test_skips_archive_by_default(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    _touch(root / "hypotheses" / "0001-a.md")
    _touch(root / "_archive" / "hypotheses" / "0002-b.md")
    found = {p.relative_to(root).as_posix() for p in iter_entity_markdown(root)}
    assert found == {"hypotheses/0001-a.md"}


def test_include_archived_unskips_only_archive(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    _touch(root / "hypotheses" / "0001-a.md")
    _touch(root / "_archive" / "hypotheses" / "0002-b.md")
    _touch(root / "_scratch" / "0003-c.md")  # other _-prefixed: still skipped
    found = {p.relative_to(root).as_posix() for p in iter_entity_markdown(root, include_archived=True)}
    assert found == {"hypotheses/0001-a.md", "_archive/hypotheses/0002-b.md"}


def test_always_skips_other_underscore_segments(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    _touch(root / "hypotheses" / "0001-a.md")
    _touch(root / "_scratch" / "0002-b.md")
    _touch(root / "hypotheses" / "_wip" / "0003-c.md")
    found = {p.relative_to(root).as_posix() for p in iter_entity_markdown(root)}
    assert found == {"hypotheses/0001-a.md"}


def test_missing_root_yields_nothing(tmp_path: Path) -> None:
    assert list(iter_entity_markdown(tmp_path / "entities")) == []


def test_deterministic_sorted_order(tmp_path: Path) -> None:
    root = tmp_path / "entities"
    for name in ("0003-c", "0001-a", "0002-b"):
        _touch(root / "hypotheses" / f"{name}.md")
    out = [p.name for p in iter_entity_markdown(root)]
    assert out == ["0001-a.md", "0002-b.md", "0003-c.md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_entity_scan.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.entity_scan`.

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/entity_scan.py
"""The sole sanctioned recursive scanner of canonical entity markdown (P3).

Archived entities live under ``entities/_archive/``. This iterator is the ONE
place that decides what counts as a live entity file: it skips any ``_``-prefixed
path segment below the entities root, and — only when ``include_archived`` is set —
un-skips the single reserved ``_archive`` subtree. Every recursive ``entities/``
scan must route through here so the archive skip cannot regress (enforced by the
guard test). Stdlib-only leaf module (no science_tool imports) to avoid cycles.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

ARCHIVE_SEGMENT = "_archive"


def iter_entity_markdown(entities_root: Path, *, include_archived: bool = False) -> Iterator[Path]:
    """Yield ``*.md`` files under ``entities_root`` in sorted order, skipping any
    ``_``-prefixed segment. When ``include_archived`` is True, the single
    ``_archive`` segment is NOT a skip reason (other ``_``-prefixed segments still
    are). Missing root yields nothing.
    """
    if not entities_root.is_dir():
        return
    for path in sorted(entities_root.rglob("*.md")):
        rel_parts = path.relative_to(entities_root).parts[:-1]  # exclude filename
        hidden = [seg for seg in rel_parts if seg.startswith("_")]
        if not hidden:
            yield path
            continue
        if include_archived and hidden == [ARCHIVE_SEGMENT]:
            yield path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_entity_scan.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entity_scan.py science/tests/test_entity_scan.py
git commit -m "feat(archive): entity_scan iterator — sole recursive entities/ scanner with _archive skip"
```

---

### Task 2: Reserved-path guard in `_resolve_local_home`

**Files:**
- Modify: `science/src/science_tool/entities.py:71-93`
- Test: `science/tests/test_resolve_local_home_reserved.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_resolve_local_home_reserved.py
"""A local kind home may not use a _-prefixed segment at any depth (P3)."""
from __future__ import annotations

import pytest

from science_tool.entities import EntityCommandError, _resolve_local_home


def test_rejects_top_level_underscore_segment() -> None:
    with pytest.raises(EntityCommandError):
        _resolve_local_home("mykind", "entities/_foo")


def test_rejects_nested_underscore_segment() -> None:
    with pytest.raises(EntityCommandError):
        _resolve_local_home("mykind", "entities/foo/_bar")


def test_rejects_archive_segment_explicitly() -> None:
    with pytest.raises(EntityCommandError):
        _resolve_local_home("mykind", "entities/_archive/mykind")


def test_accepts_normal_home() -> None:
    assert _resolve_local_home("mykind", "entities/mykind") == __import__("pathlib").Path("entities/mykind")


def test_default_home_unchanged() -> None:
    assert _resolve_local_home("mykind", None) == __import__("pathlib").Path("entities/mykind")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_resolve_local_home_reserved.py -v`
Expected: FAIL — the two `_`-prefixed cases are currently accepted (no underscore rule).

- [ ] **Step 3: Add the guard**

In `entities.py`, replace the rejection condition in `_resolve_local_home` (currently the `if (... )` block at lines 86-92) with a version that also rejects any `_`-prefixed segment:

```python
    candidate = Path(home)
    parts = candidate.parts
    if (
        candidate.is_absolute() or ".." in parts or len(parts) < 2 or parts[0] != "entities"
    ):  # len(parts) < 2 rejects the bare "entities" root (would scan top-level entities/*.md)
        raise EntityCommandError(
            f"local kind {name!r} home {home!r} must be a relative path of the form "
            "'entities/<segment>/...' with no parent traversal"
        )
    if any(seg.startswith("_") for seg in parts):
        raise EntityCommandError(
            f"local kind {name!r} home {home!r} may not contain a '_'-prefixed path "
            "segment (reserved for the archive tier; mirrors the entity_scan skip rule)"
        )
    return candidate
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_resolve_local_home_reserved.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_resolve_local_home_reserved.py
git commit -m "feat(archive): reject _-prefixed local-kind homes (mirrors entity_scan skip)"
```

---

### Task 3: Route all recursive `entities/`-rooted scans through `entity_scan` + guard test

**Files:**
- Modify: `consolidation.py:35`, `graph/storage_adapters/markdown.py:39`, `validate/checks/cross_references.py:424`, `validate/checks/id_prefixes.py:151`, `validate/checks/entity_conformance.py:205`, `validate/checks/hypotheses.py:144`, `big_picture/validator.py:79`, `entities.py:963`, `entities_inventory.py:163`
- Test: `science/tests/test_entity_scan_guard.py`

This refactor is behaviour-neutral today (no `_archive/` exists in fixtures); its deliverable is the SSOT + a guard test that fails if any recursive `entities/`-rooted `rglob` reappears outside `entity_scan.py`.

- [ ] **Step 1: Write the failing guard test**

```python
# science/tests/test_entity_scan_guard.py
"""Guard: no recursive entities/-rooted rglob('*.md') outside entity_scan.py (P3)."""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"

# Files whose `entities`-recursive scans are legitimately their own (entity_scan
# itself) or scan NON-entities/legacy roots (doc/specs/_LEGACY_ROOTS) or scan a
# single kind dir non-recursively. See design §3 exemptions.
_EXEMPT = {
    "entity_scan.py",            # the SSOT itself
    "entity_layout_migration.py",  # legacy roots migration
    "entities_inventory.py",     # _latest_activity scans project_root (skip-set, not entity_scan)
}
# Sites that scan legacy doc/specs roots, not entities/ (rglob present but exempt).
_EXEMPT_LINES = {
    ("validate/checks/id_prefixes.py", 52),       # doc/specs roots
    ("validate/checks/entity_conformance.py", 89),  # _LEGACY_ROOTS
}

_RGLOB = re.compile(r'\.rglob\(\s*["\']\*\.md["\']\s*\)')


def test_no_recursive_entities_rglob_outside_entity_scan() -> None:
    offenders: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        rel = py.relative_to(SRC).as_posix()
        if py.name in _EXEMPT:
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if not _RGLOB.search(line):
                continue
            # Only flag scans whose root is an entities/ tree. Heuristic: the line
            # (or this file) references an entities root variable. We approve by an
            # explicit allowlist of legacy/non-entities sites; everything else that
            # rglobs *.md in a file touching entities must route through entity_scan.
            if (rel, i) in {(f, n) for f, n in _EXEMPT_LINES}:
                continue
            offenders.append(f"{rel}:{i}: {line.strip()}")
    assert offenders == [], "Route these through entity_scan.iter_entity_markdown:\n" + "\n".join(offenders)
```

Note: this guard is intentionally strict — after routing the 8 sites, the only `rglob("*.md")` survivors in non-exempt files will be the legacy-root sites in the `_EXEMPT_LINES` allowlist. If a legitimate non-entities rglob exists elsewhere, add it to `_EXEMPT_LINES` with a comment (forces a deliberate decision).

- [ ] **Step 2: Run guard to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_entity_scan_guard.py -v`
Expected: FAIL — lists the unrouted entities-recursive sites (markdown.py, cross_references.py, id_prefixes.py:151, entity_conformance.py:205, hypotheses.py:144, big_picture/validator.py, entities.py, consolidation.py).

- [ ] **Step 3: Route each site through `entity_scan`**

For each file, add `from science_tool.entity_scan import iter_entity_markdown` and replace the recursive `entities/`-rooted scan. Concretely:

`consolidation.py` — replace the body of `iter_entity_frontmatter` loop:
```python
    for path in iter_entity_markdown(entities_root):
        fm = read_frontmatter(path)
        if fm and "id" in fm:
            out.append((path, fm))
```

`graph/storage_adapters/markdown.py::discover` — replace the inner `for path in sorted(root.rglob("*.md")):` with a routed scan that only applies the archive skip for the `entities` root (other scan_roots like `research/packages` keep plain rglob):
```python
            scan = iter_entity_markdown(root) if rel == "entities" else sorted(root.rglob("*.md"))
            for path in scan:
                if path.name.endswith(SIDECAR_MARKDOWN_SUFFIX):
                    continue
                ...
```
(KG ingestion ALWAYS skips `_archive/` — never pass `include_archived=True` here.)

`validate/checks/cross_references.py:424` — replace `for path in sorted(entities_dir.rglob("*.md")):` with `for path in iter_entity_markdown(entities_dir):`.

`validate/checks/id_prefixes.py:151` — the loop `for root in (ctx.project_root / "entities",): ... for path in sorted(root.rglob("*.md")):` becomes `for path in iter_entity_markdown(root):`.

`validate/checks/entity_conformance.py:205` — `root = ctx.project_root / "entities"; ... for path in sorted(root.rglob("*.md")):` becomes `for path in iter_entity_markdown(root):`.

`validate/checks/hypotheses.py:144` — same substitution for the `(ctx.project_root / "entities",)` loop.

`big_picture/validator.py:79` — `for path in entities_root.rglob("*.md"):` becomes `for path in iter_entity_markdown(entities_root):`.

`entities.py:963` (`_load_markdown_entities`) — `for path in sorted(root.rglob("*.md")):` becomes `for path in iter_entity_markdown(root):` (root is `project_root / policy.root`; the skip is a no-op for `entities/<kind>` roots and correctly skips `_archive` for any bare-`entities` policy root).

`entities_inventory.py:163` (`_latest_activity`) — NOT routed (scans whole `project_root`). Add `"_archive"` to its existing skip-set so archived files don't count as latest activity:
```python
        if any(part in {"templates", ".venv", "data", ".git", "__pycache__", "node_modules"} or part.startswith("_") for part in path.parts):
            continue
```

- [ ] **Step 4: Run guard + a broad regression slice**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_entity_scan_guard.py tests/test_consolidation_graph.py tests/test_consolidation_candidates.py -v`
Expected: guard PASSES; P1/P2 consolidation tests still PASS (behaviour-neutral).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool science/tests/test_entity_scan_guard.py
git commit -m "refactor(archive): route all recursive entities/ scans through entity_scan + guard test"
```

---

### Task 4: Archive index — models, I/O, fold, resolvable ids

**Files:**
- Create: `science/src/science_tool/archive.py`
- Test: `science/tests/test_archive_index.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_index.py
"""Append-only archive index: fold, tombstone, resolvable ids (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import (
    ArchiveRow,
    append_row,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)


def test_archive_index_path(tmp_path: Path) -> None:
    assert archive_index_path(tmp_path) == tmp_path / "entities" / "_archive" / "archive-index.jsonl"


def test_derive_archive_path_mirrors_kind_subtree() -> None:
    assert derive_archive_path("entities/interpretations/0067-x.md") == "entities/_archive/interpretations/0067-x.md"


def test_append_and_fold_last_write_wins(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    append_row(p, ArchiveRow(op="archive", id="interpretation:x", kind="interpretation",
                             aliases=["int:x-old"], same_as=["interpretation:y"],
                             original_path="entities/interpretations/x.md", archived_at="T1"))
    idx = load_archive_index(tmp_path)
    assert set(idx.active_by_id) == {"interpretation:x"}
    # alias + same_as + canonical all resolve to canonical:
    assert idx.resolvable_ids()["int:x-old"] == "interpretation:x"
    assert idx.resolvable_ids()["interpretation:y"] == "interpretation:x"
    assert idx.resolvable_ids()["interpretation:x"] == "interpretation:x"


def test_tombstone_removes_from_active(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    append_row(p, ArchiveRow(op="archive", id="interpretation:x", kind="interpretation",
                             original_path="entities/interpretations/x.md", archived_at="T1"))
    append_row(p, ArchiveRow(op="unarchive", id="interpretation:x",
                             restored_path="entities/interpretations/x.md", unarchived_at="T2"))
    idx = load_archive_index(tmp_path)
    assert idx.active_by_id == {}
    assert idx.resolvable_ids() == {}


def test_re_archive_after_unarchive_is_active(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    for op, ts in (("archive", "T1"), ("unarchive", "T2"), ("archive", "T3")):
        append_row(p, ArchiveRow(op=op, id="interpretation:x", kind="interpretation",
                                 original_path="entities/interpretations/x.md",
                                 archived_at=ts, restored_path="entities/interpretations/x.md", unarchived_at=ts))
    idx = load_archive_index(tmp_path)
    assert set(idx.active_by_id) == {"interpretation:x"}


def test_every_row_has_schema_version(tmp_path: Path) -> None:
    p = archive_index_path(tmp_path)
    append_row(p, ArchiveRow(op="archive", id="interpretation:x", original_path="entities/interpretations/x.md", archived_at="T1"))
    line = p.read_text(encoding="utf-8").splitlines()[0]
    import json
    assert json.loads(line)["schema_version"] == 1


def test_missing_index_loads_empty(tmp_path: Path) -> None:
    idx = load_archive_index(tmp_path)
    assert idx.active_by_id == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_index.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.archive`.

- [ ] **Step 3: Write the implementation**

```python
# science/src/science_tool/archive.py
"""Archive tier (P3): append-only index, relocation, and index-only resolution.

The active archive index — never archived-markdown scanning — is the source of
truth for archived-id resolution. Rows are append-only; reversal appends an
``unarchive`` tombstone. ``load_archive_index`` folds rows last-write-wins per id.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1
ARCHIVE_SEGMENT = "_archive"
DEFAULT_ARCHIVE_STATUSES = frozenset({"superseded", "archived"})


class ArchiveRow(BaseModel):
    """One append-only operation. ``op`` discriminates archive vs unarchive; the
    P4-reserved fields (digest_insight/consolidated_into/cluster_id) are simply
    absent in P3 and read via ``.get``-style optional access."""
    schema_version: int = SCHEMA_VERSION
    op: str  # "archive" | "unarchive"
    id: str
    kind: str | None = None
    title: str | None = None
    aliases: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    status: str | None = None
    superseded_by: str | None = None
    original_path: str | None = None
    archived_at: str | None = None
    reason: str | None = None
    restored_path: str | None = None
    unarchived_at: str | None = None


class ArchiveIndex(BaseModel):
    active_by_id: dict[str, ArchiveRow] = Field(default_factory=dict)

    def resolvable_ids(self) -> dict[str, str]:
        """alias/same_as/canonical -> canonical_id over ACTIVE entries only."""
        out: dict[str, str] = {}
        for canonical, row in self.active_by_id.items():
            out[canonical] = canonical
            for other in (*row.aliases, *row.same_as):
                out[other] = canonical
        return out


def archive_index_path(project_root: Path) -> Path:
    return project_root / "entities" / ARCHIVE_SEGMENT / "archive-index.jsonl"


def derive_archive_path(original_rel: str) -> str:
    """`entities/<rest>` -> `entities/_archive/<rest>` (kind subtree mirrored)."""
    parts = Path(original_rel).parts
    if not parts or parts[0] != "entities":
        raise ValueError(f"archive path must be under entities/: {original_rel!r}")
    return Path("entities", ARCHIVE_SEGMENT, *parts[1:]).as_posix()


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def append_row(index_path: Path, row: ArchiveRow) -> None:
    """Append one complete JSON line and fsync the index file + parent dir."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row.model_dump(), sort_keys=True) + "\n"
    with open(index_path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(index_path.parent)


def load_archive_index(project_root: Path) -> ArchiveIndex:
    """Fold rows last-write-wins per id; an id whose latest op is ``unarchive`` is
    dropped from the active set."""
    path = archive_index_path(project_root)
    active: dict[str, ArchiveRow] = {}
    if not path.is_file():
        return ArchiveIndex(active_by_id=active)
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        row = ArchiveRow.model_validate_json(raw)
        if row.op == "archive":
            active[row.id] = row
        elif row.op == "unarchive":
            active.pop(row.id, None)
    return ArchiveIndex(active_by_id=active)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_index.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive.py science/tests/test_archive_index.py
git commit -m "feat(archive): append-only archive index models, fold, tombstone, resolvable ids"
```

---

### Task 5: Relocate/restore mutators (report-then-apply)

**Files:**
- Modify: `science/src/science_tool/archive.py`
- Test: `science/tests/test_archive_mutators.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_mutators.py
"""archive_entities / unarchive_entities: relocate, index, reverse (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import (
    archive_entities,
    archive_index_path,
    load_archive_index,
    unarchive_entities,
)


def _write(root: Path, kind: str, name: str, fm: str) -> Path:
    d = root / "entities" / kind
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(fm, encoding="utf-8")
    return p


def _superseded(root: Path, kind: str, name: str, eid: str) -> Path:
    return _write(root, kind, name, f"---\nid: {eid}\ntype: {kind[:-1]}\nstatus: superseded\n---\nbody\n")


def test_report_lists_candidates_without_moving(tmp_path: Path) -> None:
    p = _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    report = archive_entities(tmp_path, apply=False, now="T1")
    assert [c["id"] for c in report["candidates"]] == ["interpretation:0001-x"]
    assert report["applied"] == []
    assert p.exists()  # not moved
    assert not archive_index_path(tmp_path).exists()


def test_apply_moves_and_indexes(tmp_path: Path) -> None:
    p = _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    report = archive_entities(tmp_path, apply=True, now="T1")
    assert report["applied"] == ["interpretation:0001-x"]
    assert not p.exists()
    moved = tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md"
    assert moved.exists()
    idx = load_archive_index(tmp_path)
    assert set(idx.active_by_id) == {"interpretation:0001-x"}
    assert idx.active_by_id["interpretation:0001-x"].reason == "status:superseded"
    assert idx.active_by_id["interpretation:0001-x"].original_path == "entities/interpretations/0001-x.md"


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    archive_entities(tmp_path, apply=True, now="T1")
    report2 = archive_entities(tmp_path, apply=True, now="T2")  # already relocated, not re-seen
    assert report2["candidates"] == []
    assert report2["applied"] == []


def test_only_hidden_statuses_are_candidates(tmp_path: Path) -> None:
    _write(tmp_path, "hypotheses", "0001-a", "---\nid: hypothesis:0001-a\ntype: hypothesis\nstatus: proposed\n---\n")
    _superseded(tmp_path, "interpretations", "0002-b", "interpretation:0002-b")
    report = archive_entities(tmp_path, apply=False, now="T1")
    assert [c["id"] for c in report["candidates"]] == ["interpretation:0002-b"]


def test_unarchive_restores_and_tombstones(tmp_path: Path) -> None:
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    archive_entities(tmp_path, apply=True, now="T1")
    report = unarchive_entities(tmp_path, ["interpretation:0001-x"], apply=True, now="T2")
    assert report["applied"] == ["interpretation:0001-x"]
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
    assert load_archive_index(tmp_path).active_by_id == {}


def test_unarchive_collision_fails_before_moving(tmp_path: Path) -> None:
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    archive_entities(tmp_path, apply=True, now="T1")
    # Recreate a live file at the original path -> restore must refuse.
    _superseded(tmp_path, "interpretations", "0001-x", "interpretation:0001-x")
    with pytest.raises(Exception):
        unarchive_entities(tmp_path, ["interpretation:0001-x"], apply=True, now="T2")
    # archive copy still present, no tombstone applied
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()
    assert set(load_archive_index(tmp_path).active_by_id) == {"interpretation:0001-x"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_mutators.py -v`
Expected: FAIL — `archive_entities` / `unarchive_entities` not defined.

- [ ] **Step 3: Add mutators to `archive.py`**

```python
# append to science/src/science_tool/archive.py
import shutil

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entity_scan import iter_entity_markdown


class ArchiveError(Exception):
    """Raised on an unsafe archive/unarchive operation (fail-loud)."""


def _candidate_rows(project_root: Path, statuses: frozenset[str]) -> list[ArchiveRow]:
    """Live (non-archived) entities whose status is in ``statuses``, as archive rows."""
    rows: list[ArchiveRow] = []
    entities_root = project_root / "entities"
    for path in iter_entity_markdown(entities_root):  # archive skipped -> already-archived never re-seen
        fm = read_frontmatter(path)
        if not fm or "id" not in fm:
            continue
        status = fm.get("status")
        if status not in statuses:
            continue
        original_rel = path.relative_to(project_root).as_posix()
        rows.append(
            ArchiveRow(
                op="archive",
                id=str(fm["id"]),
                kind=fm.get("type") or fm.get("kind"),
                title=fm.get("title"),
                aliases=[a for a in (fm.get("aliases") or []) if isinstance(a, str)],
                same_as=[s for s in (fm.get("same_as") or []) if isinstance(s, str)],
                status=status,
                superseded_by=fm.get("superseded_by"),
                original_path=original_rel,
                reason=f"status:{status}",
            )
        )
    return sorted(rows, key=lambda r: r.id)


def archive_entities(
    project_root: Path,
    *,
    statuses: frozenset[str] = DEFAULT_ARCHIVE_STATUSES,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    """Report-then-apply relocation of hidden-status entities into the archive.
    Apply does move-first-then-append per entity, rolling the move back if the
    index append fails."""
    project_root = Path(project_root).resolve()
    rows = _candidate_rows(project_root, statuses)
    report: dict = {"candidates": [{"id": r.id, "kind": r.kind, "status": r.status,
                                    "original_path": r.original_path, "superseded_by": r.superseded_by}
                                   for r in rows],
                    "applied": [], "skipped": []}
    if not apply:
        return report

    index_path = archive_index_path(project_root)
    for row in rows:
        assert row.original_path is not None
        src = project_root / row.original_path
        dst = project_root / derive_archive_path(row.original_path)
        if not src.exists():
            report["skipped"].append(row.id)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))  # move first
        _fsync_dir(dst.parent)
        try:
            append_row(index_path, row.model_copy(update={"archived_at": now}))
        except Exception:
            shutil.move(str(dst), str(src))  # roll back the move
            raise
        report["applied"].append(row.id)
    return report


def unarchive_entities(
    project_root: Path,
    ids: list[str],
    *,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    """Restore archived entities to their original path; append unarchive tombstone.
    Collision (target exists) fails before moving — never overwrite."""
    project_root = Path(project_root).resolve()
    idx = load_archive_index(project_root)
    report: dict = {"candidates": [], "applied": [], "skipped": []}
    plans: list[tuple[ArchiveRow, Path, Path]] = []
    for eid in ids:
        row = idx.active_by_id.get(eid)
        if row is None:
            report["skipped"].append(eid)
            continue
        assert row.original_path is not None
        dst = project_root / row.original_path
        src = project_root / derive_archive_path(row.original_path)
        if dst.exists():
            raise ArchiveError(f"cannot unarchive {eid!r}: target {row.original_path} already exists")
        if not src.exists():
            raise ArchiveError(f"cannot unarchive {eid!r}: archived file missing at {src}")
        report["candidates"].append({"id": eid, "restored_path": row.original_path})
        plans.append((row, src, dst))
    if not apply:
        return report
    index_path = archive_index_path(project_root)
    for row, src, dst in plans:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        _fsync_dir(dst.parent)
        append_row(index_path, ArchiveRow(op="unarchive", id=row.id,
                                          restored_path=row.original_path, unarchived_at=now))
        report["applied"].append(row.id)
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_mutators.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive.py science/tests/test_archive_mutators.py
git commit -m "feat(archive): status-driven archive/unarchive mutators (move-first-then-append, reversible)"
```

---

### Task 6: `verify_archive()` + validate subcheck

**Files:**
- Modify: `science/src/science_tool/archive.py`
- Modify: `science/src/science_tool/validate/checks/cross_references.py`
- Test: `science/tests/test_archive_verify.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_verify.py
"""verify_archive reconciles fs<->index and detects alias collisions (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import ArchiveRow, append_row, archive_index_path, verify_archive


def _archived_file(tmp_path: Path, rel: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\nid: x\n---\n", encoding="utf-8")


def test_clean_archive_has_no_problems(tmp_path: Path) -> None:
    _archived_file(tmp_path, "entities/_archive/interpretations/0001-x.md")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0001-x",
               original_path="entities/interpretations/0001-x.md", archived_at="T1"))
    assert verify_archive(tmp_path, live_alias_space=set()) == []


def test_moved_but_unindexed_detected(tmp_path: Path) -> None:
    _archived_file(tmp_path, "entities/_archive/interpretations/0001-x.md")  # file present, no row
    problems = verify_archive(tmp_path, live_alias_space=set())
    assert any("no active index row" in p for p in problems)


def test_indexed_but_missing_file_detected(tmp_path: Path) -> None:
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0001-x",
               original_path="entities/interpretations/0001-x.md", archived_at="T1"))  # no file moved
    problems = verify_archive(tmp_path, live_alias_space=set())
    assert any("file missing" in p for p in problems)


def test_alias_collision_with_live_space_detected(tmp_path: Path) -> None:
    _archived_file(tmp_path, "entities/_archive/interpretations/0001-x.md")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0001-x",
               aliases=["shared-alias"], original_path="entities/interpretations/0001-x.md", archived_at="T1"))
    problems = verify_archive(tmp_path, live_alias_space={"shared-alias"})
    assert any("collides" in p for p in problems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_verify.py -v`
Expected: FAIL — `verify_archive` not defined.

- [ ] **Step 3: Implement `verify_archive` and wire the subcheck**

Append to `archive.py`:
```python
def verify_archive(project_root: Path, live_alias_space: set[str]) -> list[str]:
    """Reconcile filesystem <-> active index and detect alias collisions against
    the live resolver's full alias space. Returns a list of problem strings
    (empty == clean). ``live_alias_space`` = live canonical ids + aliases + same_as
    + manual aliases (the build_alias_map domain)."""
    project_root = Path(project_root).resolve()
    idx = load_archive_index(project_root)
    problems: list[str] = []

    # (a) every active row's file must exist at its derived archive path
    archived_present: set[str] = set()
    for eid, row in idx.active_by_id.items():
        assert row.original_path is not None
        dst = project_root / derive_archive_path(row.original_path)
        if dst.exists():
            archived_present.add(dst.resolve().as_posix())
        else:
            problems.append(f"active archive row {eid!r}: file missing at {derive_archive_path(row.original_path)}")

    # (b) every _archive/ markdown file must have an active row
    archive_root = project_root / "entities" / ARCHIVE_SEGMENT
    if archive_root.is_dir():
        for path in sorted(archive_root.rglob("*.md")):
            if path.resolve().as_posix() not in archived_present:
                rel = path.relative_to(project_root).as_posix()
                problems.append(f"archived file {rel} has no active index row")

    # (c) alias collisions: archive id/alias/same_as vs the live alias space
    resolvable = idx.resolvable_ids()
    for token, canonical in sorted(resolvable.items()):
        if token != canonical and token in resolvable and resolvable[token] != canonical:
            problems.append(f"archive alias {token!r} maps to multiple canonical ids")
        if token in live_alias_space:
            problems.append(f"archive id/alias {token!r} collides with the live alias space")
    return problems
```

In `validate/checks/cross_references.py`, add a new Check that runs `verify_archive` with the live alias space assembled from `all_ids` plus loaded aliases. Add after `check_cross_references`:
```python
@Check(section="archive index reconciliation", order=21)
def check_archive_index(ctx: ValidateContext) -> Iterator[Result]:
    from science_tool.archive import verify_archive
    from science_tool.graph.sources import build_alias_map, load_project_sources

    try:
        sources = load_project_sources(ctx.project_root)
        live_space = set(build_alias_map(sources.entities, manual_aliases=sources.manual_aliases))
    except Exception:
        live_space = set()
    problems = verify_archive(ctx.project_root, live_alias_space=live_space)
    if not problems:
        yield _result(Severity.INFO, "Archive index consistent")
        return
    for problem in problems:
        yield _result(Severity.ERROR, f"Archive index: {problem}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_verify.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive.py science/src/science_tool/validate/checks/cross_references.py science/tests/test_archive_verify.py
git commit -m "feat(archive): verify_archive reconciler + validate subcheck (fail-loud)"
```

---

### Task 7: Archive-aware resolution in `validate` cross-references

**Files:**
- Modify: `science/src/science_tool/validate/checks/cross_references.py:419-436`
- Test: `science/tests/test_archive_resolution_validate.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_resolution_validate.py
"""A live ref to an archived id resolves (not dangling); unknown still flagged (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.validate.checks.cross_references import check_cross_references
from science_tool.validate.context import ValidateContext


def _write(root: Path, kind: str, name: str, body: str) -> None:
    d = root / "entities" / kind
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(body, encoding="utf-8")


def _ctx(tmp_path: Path) -> ValidateContext:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    return ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)


def test_ref_to_archived_id_resolves(tmp_path: Path) -> None:
    _write(tmp_path, "interpretations", "0001-live",
           "---\nid: interpretation:0001-live\ntype: interpretation\nrelated:\n  - interpretation:0002-gone\n---\n")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-gone",
               original_path="entities/interpretations/0002-gone.md", archived_at="T1"))
    msgs = [r.message for r in check_cross_references(_ctx(tmp_path))]
    assert not any("0002-gone" in m and "not found" in m for m in msgs)


def test_unknown_ref_still_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "interpretations", "0001-live",
           "---\nid: interpretation:0001-live\ntype: interpretation\nrelated:\n  - interpretation:0099-typo\n---\n")
    msgs = [r.message for r in check_cross_references(_ctx(tmp_path))]
    assert any("0099-typo" in m and "not found" in m for m in msgs)
```

Note: `ValidateContext.from_project_root(root, *, strict, verbose)` calls `resolve_paths(root)`, which needs a valid `science.yaml`. The `name: t` minimal manifest suffices; if `resolve_paths` rejects it, mirror the manifest from an existing `tests/` validate-check test.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_resolution_validate.py -v`
Expected: FAIL — the archived ref is reported "not found".

- [ ] **Step 3: Union archive resolvable ids into `all_ids`**

In `check_cross_references`, after `all_ids.update(_load_terms_ids(...))` (line 435), add:
```python
    from science_tool.archive import load_archive_index
    all_ids.update(load_archive_index(ctx.project_root).resolvable_ids())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_resolution_validate.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/cross_references.py science/tests/test_archive_resolution_validate.py
git commit -m "feat(archive): validate resolves refs to archived ids via the index"
```

---

### Task 8: Graph archive-aware resolution + tombstone stub node

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Test: `science/tests/test_archive_resolution_graph.py`

Covers the three acceptance edge types (`related:`, `source_refs:`, `relations[].target`). The graph build pre-loads the active archive index and, where an edge target resolves to an active archived id with no live entity, materializes the edge to the canonical URI and emits a tombstone stub node from index metadata only.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_resolution_graph.py
"""Graph: edges to archived ids materialize to a stub node; files not rehydrated (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path

rdflib = pytest.importorskip("rdflib")


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")


def _live(tmp_path: Path, body: str) -> None:
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "0001-live.md").write_text(body, encoding="utf-8")


def _build_graph_text(tmp_path: Path) -> str:
    # materialize_graph(project_root, *, strict) writes knowledge/graph.trig and
    # RETURNS its Path. strict=False skips the data-package migration gate.
    from science_tool.graph.materialize import materialize_graph
    out_path = materialize_graph(tmp_path, strict=False)
    return out_path.read_text(encoding="utf-8")


def test_related_ref_to_archived_id_makes_stub_and_edge(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(tmp_path, "---\nid: interpretation:0001-live\ntype: interpretation\n"
                    "related:\n  - interpretation:0002-gone\n---\n")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-gone",
               kind="interpretation", title="Gone v1", superseded_by="interpretation:0003-new",
               original_path="entities/interpretations/0002-gone.md", archived_at="T1"))
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0003-new",
               kind="interpretation", title="New", original_path="entities/interpretations/0003-new.md", archived_at="T1"))
    text = _build_graph_text(tmp_path)
    assert "0002-gone" in text                        # edge target present
    assert "ArchivedEntity" in text                   # stub typed
    assert "Gone v1" in text                           # label from index
    assert "supersededBy" in text                      # superseded_by resolvable -> emitted


def test_unknown_ref_makes_no_stub(tmp_path: Path) -> None:
    _seed(tmp_path)
    _live(tmp_path, "---\nid: interpretation:0001-live\ntype: interpretation\n"
                    "related:\n  - interpretation:0099-typo\n---\n")
    text = _build_graph_text(tmp_path)
    assert "ArchivedEntity" not in text
    assert "0099-typo" not in text
```

Notes for the implementer: (1) asserts on serialized TriG substrings to stay robust to URI scheme details. (2) Match the exact predicate CURIEs at the three graph edge sites and `SCI_NS` to `graph/materialize.py`. (3) **Fixture risk:** `materialize_graph` builds the whole project graph; if the minimal `science.yaml`/entities fixture is rejected by the build (e.g. `resolve_paths`/profile requirements), mirror the project scaffold from an existing graph-build test under `tests/` (search `materialize_graph(` in tests).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_resolution_graph.py -v`
Expected: FAIL — no stub node emitted (edge currently dropped silently).

- [ ] **Step 3: Implement archive-aware resolution + stub emission**

In `materialize.py`, the edge-resolution logic lives in the inner materialization function (where `resolver` and `entity_index` are created, ~line 126), while `project_root` enters at the public `materialize_graph` (line 219). Thread `project_root` (or the loaded `archive_active`/`archive_resolvable`) into that inner function. Load the active archive index once near the resolver:
```python
    from science_tool.archive import load_archive_index
    archive_active = load_archive_index(project_root).active_by_id  # canonical_id -> ArchiveRow
    archive_resolvable = {  # alias/same_as/canonical -> canonical archived id
        token: cid for cid, row in archive_active.items()
        for token in (cid, *row.aliases, *row.same_as)
    }
    referenced_archived: set[str] = set()
```

Add a helper near `_entity_uri` (~line 1183):
```python
def _archived_target_uri(raw_target: str, resolver, entity_index, archive_resolvable, referenced_archived):
    """If raw_target resolves to an ACTIVE archived id (and is not a live entity),
    return its canonical URI and record it for stub emission. Else None."""
    res = resolver.resolve(raw_target, allow_cross_kind_fallback=True)
    cid = res.canonical_id if res.status == "resolved" else None
    cid = cid or archive_resolvable.get(raw_target)
    if cid is None or cid in entity_index:  # live entity wins; not an archived-only target
        return None
    archived = archive_resolvable.get(cid)
    if archived is None:
        return None
    referenced_archived.add(archived)
    return _entity_uri(archived)
```

At each of the three acceptance edge sites — the `related:`, `source_refs:`, and `relations[].target` resolution loops — where the code currently does `if resolution.status != "resolved": continue` (or `entity_index.get(...) is None: continue`), insert a fallback BEFORE the `continue` that adds the edge to the archived URI:
```python
        archived_uri = _archived_target_uri(raw_target, resolver, entity_index, archive_resolvable, referenced_archived)
        if archived_uri is not None:
            knowledge.add((entity_uri, <SAME_PREDICATE_AS_THIS_EDGE>, archived_uri))
        continue
```
(Use the same predicate the live branch uses for that edge type, e.g. `SCI_NS.related` / `SCI_NS.hasSource` / the relation's resolved predicate — match the live code at each site.)

After the per-entity loop (before serializing), emit one stub node per referenced archived id:
```python
    for archived_id in sorted(referenced_archived):
        row = archive_active[archived_id]
        uri = _entity_uri(archived_id)
        knowledge.add((uri, RDF.type, SCI_NS.ArchivedEntity))
        if row.kind:
            knowledge.add((uri, SCI_NS.entityKind, Literal(row.kind)))
        if row.title:
            knowledge.add((uri, RDFS.label, Literal(row.title)))
        knowledge.add((uri, SCI_NS.archived, Literal(True)))
        if row.superseded_by and row.superseded_by in archive_resolvable:
            knowledge.add((uri, SCI_NS.supersededBy, _entity_uri(archive_resolvable[row.superseded_by])))
```
Confirm `RDF`, `RDFS`, `Literal`, and `SCI_NS` are imported at the top of `materialize.py` (they are used elsewhere; add any missing import). If `SCI_NS.ArchivedEntity` / `entityKind` / `archived` / `supersededBy` are new terms, that is fine — `SCI_NS` is a namespace object that mints terms on demand.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_resolution_graph.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_archive_resolution_graph.py
git commit -m "feat(archive): graph resolves archived refs to canonical URI + tombstone stub node"
```

---

### Task 9: `science entities archive` / `unarchive` CLI

**Files:**
- Modify: `science/src/science_tool/cli.py` (after the `mark-superseded` command, ~line 286)
- Test: `science/tests/test_archive_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_archive_cli.py
"""CLI: science entities archive / unarchive (report-then-apply) (P3)."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _superseded(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "0001-x.md").write_text("---\nid: interpretation:0001-x\ntype: interpretation\nstatus: superseded\n---\n", encoding="utf-8")


def test_archive_report_then_apply(tmp_path: Path) -> None:
    _superseded(tmp_path)
    r1 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path)])
    assert r1.exit_code == 0, r1.output
    assert "interpretation:0001-x" in r1.output
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # dry run

    r2 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    assert r2.exit_code == 0, r2.output
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()


def test_unarchive_restores(tmp_path: Path) -> None:
    _superseded(tmp_path)
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    r = CliRunner().invoke(main, ["entities", "unarchive", "interpretation:0001-x", "--project-root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_cli.py -v`
Expected: FAIL — `No such command 'archive'`.

- [ ] **Step 3: Add the commands (mirror `mark-superseded`)**

```python
@entities_group.command("archive")
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."), help="Project root (default: current directory).")
@click.option("--status", "statuses", multiple=True, help="Statuses to archive (default: superseded, archived).")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_archive_command(project_root: Path, statuses: tuple[str, ...], apply_changes: bool) -> None:
    """Relocate hidden-status entities into entities/_archive/ (report, then --apply)."""
    from science_tool.archive import DEFAULT_ARCHIVE_STATUSES, archive_entities
    from datetime import datetime, timezone

    status_set = frozenset(statuses) if statuses else DEFAULT_ARCHIVE_STATUSES
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = archive_entities(project_root, statuses=status_set, apply=apply_changes, now=now)
    click.echo(json.dumps(report, indent=2))


@entities_group.command("unarchive")
@click.argument("ids", nargs=-1, required=True)
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."), help="Project root (default: current directory).")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_unarchive_command(ids: tuple[str, ...], project_root: Path, apply_changes: bool) -> None:
    """Restore archived entities to their original path (report, then --apply)."""
    from science_tool.archive import unarchive_entities
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = unarchive_entities(project_root, list(ids), apply=apply_changes, now=now)
    click.echo(json.dumps(report, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_cli.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_archive_cli.py
git commit -m "feat(archive): science entities archive / unarchive CLI"
```

---

### Task 10: `science search --archived` top-level command

**Files:**
- Modify: `science/src/science_tool/cli.py` (top-level command, near other `@main.command`/`@click.group` registrations)
- Test: `science/tests/test_search_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_search_cli.py
"""science search --archived reads the index; fails loud without --archived (P3)."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.cli import main


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-dag-v1",
               kind="interpretation", title="Parameter derivation DAG", aliases=["dag-old"],
               original_path="entities/interpretations/0002-dag-v1.md", archived_at="T1"))


def test_search_archived_matches_title(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["search", "derivation", "--archived", "--project-root", str(tmp_path), "--format", "json"])
    assert r.exit_code == 0, r.output
    hits = json.loads(r.output)
    assert [h["id"] for h in hits] == ["interpretation:0002-dag-v1"]


def test_search_archived_matches_alias(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["search", "dag-old", "--archived", "--project-root", str(tmp_path), "--format", "json"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)[0]["id"] == "interpretation:0002-dag-v1"


def test_search_without_archived_fails_loud(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["search", "derivation", "--project-root", str(tmp_path)])
    assert r.exit_code != 0
    assert "--archived" in r.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_search_cli.py -v`
Expected: FAIL — `No such command 'search'`.

- [ ] **Step 3: Add the command + the search function**

Add a search function to `archive.py`:
```python
def search_archive(project_root: Path, query: str) -> list[dict]:
    """Case-insensitive substring search over active archive entries
    (id, title, kind, aliases, same_as). Returns sorted hit dicts."""
    q = query.lower()
    idx = load_archive_index(Path(project_root).resolve())
    hits: list[dict] = []
    for cid, row in idx.active_by_id.items():
        haystack = " ".join(filter(None, [cid, row.title or "", row.kind or "", *row.aliases, *row.same_as])).lower()
        if q in haystack:
            hits.append({"id": cid, "kind": row.kind, "title": row.title,
                         "status": row.status, "original_path": row.original_path})
    return sorted(hits, key=lambda h: h["id"])
```

Add the top-level command to `cli.py` (register on the root `main` group):
```python
@main.command("search")
@click.argument("query")
@click.option("--archived", is_flag=True, default=False, help="Search the archive index (required; live search not yet implemented).")
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."), help="Project root (default: current directory).")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json", show_default=True)
def search_command(query: str, archived: bool, project_root: Path, output_format: str) -> None:
    """Search entities. P3 supports --archived only (reads the archive index)."""
    if not archived:
        raise click.UsageError("science search currently supports only --archived (live entity search is not implemented).")
    from science_tool.archive import search_archive

    hits = search_archive(project_root, query)
    if output_format == "json":
        click.echo(json.dumps(hits, indent=2, sort_keys=True))
    else:
        for h in hits:
            click.echo(f"{h['id']}  [{h['kind']}]  {h['title'] or ''}")
```
(If `main` is not the group object name in `cli.py`, register on whatever the root `click.group()` is — read the top of `cli.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_search_cli.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/archive.py science/src/science_tool/cli.py science/tests/test_search_cli.py
git commit -m "feat(archive): science search --archived (index-backed; fail-loud without flag)"
```

---

### Task 11: `science entities list --include-archived` (index-merge) + `.rgignore`

**Files:**
- Modify: `science/src/science_tool/entities.py:719-752` (`list_entities`)
- Modify: the `science entity list` CLI command in `cli.py:637` (`entity_group`, function `entity_list`, calls `list_entities(Path.cwd(), …)`)
- Create: `.rgignore` (repo root)
- Test: `science/tests/test_list_include_archived.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_list_include_archived.py
"""list_entities(include_archived=True) merges archive-origin rows, tagged (P3)."""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.entities import list_entities


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "0001-live.md").write_text("---\nid: interpretation:0001-live\ntype: interpretation\nstatus: complete\n---\n", encoding="utf-8")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-gone",
               kind="interpretation", title="Gone", status="superseded",
               original_path="entities/interpretations/0002-gone.md", archived_at="T1"))


def test_default_excludes_archived(tmp_path: Path) -> None:
    _seed(tmp_path)
    ids = {row["id"] for row in list_entities(tmp_path)}
    assert ids == {"interpretation:0001-live"}


def test_include_archived_merges_tagged_rows(tmp_path: Path) -> None:
    _seed(tmp_path)
    rows = list_entities(tmp_path, include_archived=True)
    by_id = {r["id"]: r for r in rows}
    assert "interpretation:0002-gone" in by_id
    assert by_id["interpretation:0002-gone"].get("archived") is True
    assert by_id["interpretation:0001-live"].get("archived") in (False, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_list_include_archived.py -v`
Expected: FAIL — `list_entities` has no `include_archived` parameter.

- [ ] **Step 3: Add the index-merge to `list_entities`**

Change the signature and append archive rows (index-only; never loads archived markdown). Update `list_entities`:
```python
def list_entities(
    project_root: Path,
    kind: str | None = None,
    status: str | None = None,
    related: str | None = None,
    *,
    include_hidden: bool = False,
    include_archived: bool = False,
) -> list[dict[str, str]]:
    sources = load_project_sources(project_root.resolve())
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    related_key = _resolved_ref_key(resolver, related) if related is not None else None

    rows: list[dict[str, str]] = []
    for entity in sources.entities:
        if kind is not None and entity.kind != kind:
            continue
        entity_status = entity.status or ""
        if status is not None:
            if entity_status != status:
                continue
        elif not include_hidden and not is_default_visible(entity.status):
            continue
        if related_key is not None and not _related_refs_match(entity.related, related_key, resolver):
            continue
        rows.append(
            {
                "id": entity.canonical_id,
                "kind": entity.kind,
                "title": entity.title,
                "status": entity_status,
                "path": entity.file_path,
                "archived": False,
            }
        )
    if include_archived:
        from science_tool.archive import load_archive_index

        for cid, arow in load_archive_index(project_root.resolve()).active_by_id.items():
            if kind is not None and arow.kind != kind:
                continue
            if status is not None and (arow.status or "") != status:
                continue
            rows.append(
                {
                    "id": cid,
                    "kind": arow.kind or "",
                    "title": arow.title or "",
                    "status": arow.status or "",
                    "path": arow.original_path or "",
                    "archived": True,
                }
            )
    return sorted(rows, key=lambda row: row["id"])
```

Add `--include-archived` to the `entity list` CLI command (`entity_list` at `cli.py:637`): add `@click.option("--include-archived", is_flag=True, default=False, help="Include archived (relocated) entities from the archive index.")`, add the `include_archived: bool` param, and pass `include_archived=include_archived` to the `list_entities(Path.cwd(), …)` call. (Add an `"Archived"` column to the `emit_query_rows` columns if you want it surfaced in table output — optional.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_list_include_archived.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Add `.rgignore` and commit**

Create `.rgignore` at the repo root (worktree root) with:
```
# Archived entities are tool-retrievable via `science search --archived`.
# Hidden from plain ripgrep for ergonomics; override with `rg --no-ignore`.
entities/_archive/
```

```bash
git add science/src/science_tool/entities.py science/src/science_tool/cli.py science/tests/test_list_include_archived.py .rgignore
git commit -m "feat(archive): entities list --include-archived (index-merge, tagged) + .rgignore"
```

---

### Task 12: P3 acceptance integration test

**Files:**
- Test: `science/tests/test_archive_acceptance.py`

The P3 acceptance invariant: after `archive --apply` on a *referenced* superseded entity, `science validate` passes (no new dangling) and graph build materializes the edge to a stub node, and the archived file is not scanned as a live entity.

- [ ] **Step 1: Write the acceptance test**

```python
# science/tests/test_archive_acceptance.py
"""End-to-end P3 invariant: archive a referenced superseded entity, then
validate + graph build stay healthy and the file is not live (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.sources import load_project_sources

rdflib = pytest.importorskip("rdflib")


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    # live entity references the soon-to-be-archived one via related + relations + source_refs
    (d / "0001-live.md").write_text(
        "---\nid: interpretation:0001-live\ntype: interpretation\nstatus: complete\n"
        "related:\n  - interpretation:0002-gone\n"
        "source_refs:\n  - interpretation:0002-gone\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-gone\n---\n",
        encoding="utf-8")
    (d / "0002-gone.md").write_text(
        "---\nid: interpretation:0002-gone\ntype: interpretation\nstatus: superseded\ntitle: Gone v1\n---\n",
        encoding="utf-8")


def test_archive_then_file_not_live(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    ids = {e.canonical_id for e in load_project_sources(tmp_path).entities}
    assert "interpretation:0002-gone" not in ids        # not scanned as a live entity
    assert "interpretation:0001-live" in ids


def test_archive_then_graph_edge_and_stub(tmp_path: Path) -> None:
    _seed(tmp_path)
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    from science_tool.graph.materialize import materialize_graph
    text = materialize_graph(tmp_path, strict=False).read_text(encoding="utf-8")
    assert "ArchivedEntity" in text
    assert "Gone v1" in text


def test_archive_then_validate_no_new_dangling(tmp_path: Path) -> None:
    _seed(tmp_path)
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    from science_tool.validate.checks.cross_references import check_cross_references
    from science_tool.validate.context import ValidateContext
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    msgs = [r.message for r in check_cross_references(ctx)]
    assert not any("0002-gone" in m and "not found" in m for m in msgs)
```

Note: same fixture-completeness caveat as Task 8 — if `materialize_graph` / `from_project_root` reject the minimal fixture, mirror an existing graph-build/validate test's project scaffold.

- [ ] **Step 2: Run the acceptance test**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_archive_acceptance.py -v`
Expected: PASS (3 tests).

- [ ] **Step 3: Run the full archive suite + a regression slice**

Run: `cd science && PYTHONPATH=src rtk /home/keith/d/science/science/.venv/bin/pytest tests/test_entity_scan.py tests/test_entity_scan_guard.py tests/test_archive_index.py tests/test_archive_mutators.py tests/test_archive_verify.py tests/test_archive_resolution_validate.py tests/test_archive_resolution_graph.py tests/test_archive_cli.py tests/test_search_cli.py tests/test_list_include_archived.py tests/test_archive_acceptance.py tests/test_consolidation_candidates.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_archive_acceptance.py
git commit -m "test(archive): P3 acceptance invariant — referenced superseded entity stays resolvable"
```

---

## Self-review checklist (run before handing to execution)

- **Spec coverage:** §1 two-axis (Tasks 1, 11) · §2 modules (1, 4) · §3 iterator + reserved-path + guard (1, 2, 3) · §4 index schema/atomicity (4, 5) · §5 resolution invariant + verify + stub (6, 7, 8) · §6 mutators (5, 9) · §7 search + include-archived + .rgignore (10, 11) · §8 tests (every task) · acceptance invariant (12).
- **Deferred (flagged):** big-picture `--include-archived` deep-read → P4; non-acceptance graph edge predicates → additive follow-up.
- **Type consistency:** `iter_entity_markdown(root, *, include_archived)`, `ArchiveRow`, `load_archive_index().active_by_id` / `.resolvable_ids()`, `archive_entities(...apply, now)`, `unarchive_entities(ids, ...)`, `verify_archive(project_root, live_alias_space)`, `search_archive(project_root, query)` are used identically across tasks.
- **Pinned APIs** (verified against the repo): `ValidateContext.from_project_root(root, *, strict, verbose)` (`validate/context.py`); `materialize_graph(project_root, *, strict=True) -> Path` writes/returns `knowledge/graph.trig` (`graph/materialize.py:219`); root group is `main`, archive/unarchive go on `entities_group` (`@main.group("entities")`, `cli.py:232`), `search` on `main`; the list command is `entity list` (`entity_group`, `entity_list`, `cli.py:637`, uses `Path.cwd()`).
- **Still requires in-repo confirmation** (noted inline): the exact predicate CURIEs at the three graph edge-resolution sites + `SCI_NS`/`RDF`/`RDFS`/`Literal` imports in `materialize.py`; whether the minimal tmp_path fixture is rich enough for `materialize_graph`/`from_project_root` (else mirror an existing graph/validate test scaffold).

# Phase 5k Retired Edge Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science dag archive-retired-edges`, a narrow plan/apply surface that moves fully closed retired `*.edges.yaml` files out of the active DAG directory and into `archive/dag-retired-edges/`.

**Architecture:** Implement a focused `science_tool.dag.retired_edge_archive` module that wraps the existing Phase 5j retired-edge migration planner. Dry-run reports file state and row-closure state; apply recomputes the plan, moves one file, writes one manifest, and rolls the move back if manifest writing fails. CLI wiring stays flat under `science dag`.

**Tech Stack:** Python 3.12, Click, pytest, dataclasses, JSON manifests, existing `science_tool.dag.retired_edge_migration` and `science_tool.dag.paths` helpers.

---

## File Structure

- Create: `science/src/science_tool/dag/retired_edge_archive.py`
  - Owns archive path derivation, archive plan/result dataclasses, JSON/table rendering, dry-run planning, apply, manifest writing, SHA-256 checks, and partial-state classification.
  - Imports `build_retired_edge_migration_plan` but does not change migration classification.
- Modify: `science/src/science_tool/dag/cli.py`
  - Adds flat command `archive-retired-edges`.
  - Catches `ValueError`/filesystem errors as `click.ClickException`.
- Create: `science/tests/dag/test_retired_edge_archive.py`
  - Unit-level plan/apply tests for filesystem state, row closure, manifest content, rollback, and archived-file invisibility to active retired-edge scans.
- Modify: `science/tests/dag/test_cli.py`
  - CLI JSON/table/apply tests.
  - Help listing test update.
- Modify: `science/tests/test_cli_surface_contract.py`
  - Add the new command to the `--project` allowlist and project-root alias set.
- No design-doc edits are required during implementation unless review discovers a spec mismatch.

## Design Decisions Locked By This Plan

- Dry-run can return `status: "blocked"` with exit code 0. It is a diagnostic plan surface.
- `--apply` succeeds only for `ready_to_archive` or a complete previous archive (`already_archived`). Applying a blocked or ambiguous plan exits non-zero.
- A successful apply returns final status `already_archived` with `applied: true`. A rerun returns `already_archived` with `applied: false`.
- The manifest is strict JSON with sorted keys. Invalid or mismatched existing manifests make the state `ambiguous_state`.
- `archive/dag-retired-edges/` is a project artifact archive, not the entity archive index.
- The SHA-256 recheck in apply guards against source bytes changing between the
  in-function plan build and the move. The CLI does not accept a saved dry-run
  plan artifact.

---

### Task 1: Specify Archive Plan States

**Files:**
- Create: `science/tests/dag/test_retired_edge_archive.py`
- Create: `science/src/science_tool/dag/retired_edge_archive.py`

- [ ] **Step 1: Write failing unit tests for dry-run state classification**

Create `science/tests/dag/test_retired_edge_archive.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.dag.retired_edge_archive import (
    ARCHIVE_SCHEMA_VERSION,
    build_retired_edge_archive_plan,
)


def _write_manifest(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")


def _dag_dir(project: Path) -> Path:
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True, exist_ok=True)
    return dag_dir


def _write_retired_edge_project(project: Path) -> None:
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
source_dot: doc/figures/dags/h1.dot
edges:
  - id: 1
    source: a
    target: b
    relation: biases
    original_label: biases
    edge_status: supported
    identification: observational
    description: A retired claim that should become a reviewed migration row.
    data_support:
      - task: t001
        description: Completed task support.
    lit_support:
      - paper: Smith2020
        description: Literature support.
""".strip(),
        encoding="utf-8",
    )


def _write_lineage_proposition(project: Path) -> None:
    prop_dir = project / "entities/propositions"
    prop_dir.mkdir(parents=True, exist_ok=True)
    (prop_dir / "a-affects-b.md").write_text(
        """---
id: proposition:a-affects-b
type: proposition
title: A affects B
status: active
subject: a
predicate: affects
object: b
polarity: positive
claim_layer: causal_effect
identification_strength: observational
legacy_relation_label: biases
legacy_patch: h1
legacy_edge_id: 1
---

A affects B.
""",
        encoding="utf-8",
    )


def _archive_path(project: Path, dag: str = "h1") -> Path:
    return project / "archive/dag-retired-edges" / f"{dag}.edges.yaml"


def _manifest_path(project: Path, dag: str = "h1") -> Path:
    return project / "archive/dag-retired-edges" / f"{dag}.edges.yaml.archive.json"


def test_archive_plan_ready_for_all_closed_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    plan = build_retired_edge_archive_plan(project, dag="h1")
    payload = plan.to_json()

    assert payload["status"] == "ready_to_archive"
    assert payload["applied"] is False
    assert payload["dag"] == "h1"
    assert payload["source"] == "doc/figures/dags/h1.edges.yaml"
    assert payload["archive"] == "archive/dag-retired-edges/h1.edges.yaml"
    assert payload["manifest"] == "archive/dag-retired-edges/h1.edges.yaml.archive.json"
    assert payload["closed_rows"] == 1
    assert payload["closed_by"] == ["proposition:a-affects-b"]
    assert payload["sha256"].startswith("sha256:")
    assert payload["blockers"] == []
    assert payload["row_status_counts"] == {"closed": 1}


def test_archive_plan_blocks_non_closed_rows(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "blocked"
    assert payload["closed_rows"] == 0
    assert payload["closed_by"] == []
    assert payload["row_status_counts"] == {"blocked": 1}
    assert payload["blockers"] == ["not-all-retired-edge-rows-closed"]


def test_archive_plan_blocks_empty_retired_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = _dag_dir(project)
    (dag_dir / "h1.edges.yaml").write_text("dag: h1\nedges: []\n", encoding="utf-8")

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["empty-retired-edge-file"]
    assert payload["row_status_counts"] == {}


def test_archive_plan_missing_source_without_archive_blocks(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _dag_dir(project)

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["retired-edge-file-missing"]
    assert payload["source"] == "doc/figures/dags/h1.edges.yaml"
    assert payload["archive"] == "archive/dag-retired-edges/h1.edges.yaml"


def test_archive_plan_reports_already_archived(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")
    _manifest_path(project).write_text(
        json.dumps(
            {
                "schema_version": ARCHIVE_SCHEMA_VERSION,
                "dag": "h1",
                "original_path": "doc/figures/dags/h1.edges.yaml",
                "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
                "closed_by": ["proposition:a-affects-b"],
                "closed_rows": 1,
                "sha256": "sha256:example",
                "archived_at": "2026-07-05",
                "tool": "science dag archive-retired-edges",
                "reason": "all-retired-edges-closed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "already_archived"
    assert payload["applied"] is False
    assert payload["closed_rows"] == 1
    assert payload["closed_by"] == ["proposition:a-affects-b"]
    assert payload["blockers"] == []


def test_archive_plan_reports_ambiguous_state_for_source_and_archive(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    archived = _archive_path(project)
    archived.parent.mkdir(parents=True)
    archived.write_text("archived yaml\n", encoding="utf-8")

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["source-and-archive-both-exist"]


def test_archive_plan_reports_ambiguous_state_for_manifest_without_archive(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _manifest_path(project).parent.mkdir(parents=True)
    _manifest_path(project).write_text("{}\n", encoding="utf-8")

    payload = build_retired_edge_archive_plan(project, dag="h1").to_json()

    assert payload["status"] == "ambiguous_state"
    assert payload["blockers"] == ["archive-manifest-mismatch"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/dag/test_retired_edge_archive.py -q
```

Expected: FAIL during import because `science_tool.dag.retired_edge_archive` does not exist.

- [ ] **Step 3: Create the archive module with plan dataclasses and dry-run logic**

Create `science/src/science_tool/dag/retired_edge_archive.py`:

```python
"""Archive closed retired DAG ``*.edges.yaml`` files.

This module is intentionally narrower than the entity archive. Retired edge
files are source artifacts, not entity records, so they get a project artifact
archive path plus a small manifest.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from science_tool.dag.paths import load_dag_paths
from science_tool.dag.retired_edge_migration import build_retired_edge_migration_plan


ARCHIVE_SCHEMA_VERSION = 1
ARCHIVE_DIR = Path("archive/dag-retired-edges")
ARCHIVE_TOOL = "science dag archive-retired-edges"
ARCHIVE_REASON = "all-retired-edges-closed"

RetiredEdgeArchiveStatus = Literal[
    "ready_to_archive",
    "blocked",
    "already_archived",
    "ambiguous_state",
]


@dataclass(frozen=True)
class RetiredEdgeArchivePlan:
    project_root: str
    dag: str
    status: RetiredEdgeArchiveStatus
    source: str
    archive: str
    manifest: str
    closed_rows: int = 0
    closed_by: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)
    row_status_counts: dict[str, int] = field(default_factory=dict)
    sha256: str | None = None
    applied: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "dag": self.dag,
            "status": self.status,
            "applied": self.applied,
            "source": self.source,
            "archive": self.archive,
            "manifest": self.manifest,
            "closed_rows": self.closed_rows,
            "closed_by": list(self.closed_by),
            "blockers": list(self.blockers),
            "row_status_counts": dict(sorted(self.row_status_counts.items())),
            "sha256": self.sha256,
        }


def build_retired_edge_archive_plan(project_root: Path, *, dag: str) -> RetiredEdgeArchivePlan:
    project_root = Path(project_root).resolve()
    source, archive, manifest = _paths(project_root, dag)
    rel_source = _relative(project_root, source)
    rel_archive = _relative(project_root, archive)
    rel_manifest = _relative(project_root, manifest)

    source_exists = source.exists()
    archive_exists = archive.exists()
    manifest_exists = manifest.exists()

    if source_exists and archive_exists:
        return _plan(
            project_root,
            dag,
            status="ambiguous_state",
            source=rel_source,
            archive=rel_archive,
            manifest=rel_manifest,
            blockers=("source-and-archive-both-exist",),
        )

    if archive_exists != manifest_exists:
        return _plan(
            project_root,
            dag,
            status="ambiguous_state",
            source=rel_source,
            archive=rel_archive,
            manifest=rel_manifest,
            blockers=("archive-manifest-mismatch",),
        )

    if not source_exists and archive_exists and manifest_exists:
        try:
            manifest_payload = _read_manifest(manifest, dag=dag, archive=rel_archive, source=rel_source)
        except ValueError:
            return _plan(
                project_root,
                dag,
                status="ambiguous_state",
                source=rel_source,
                archive=rel_archive,
                manifest=rel_manifest,
                blockers=("invalid-archive-manifest",),
            )
        return _plan(
            project_root,
            dag,
            status="already_archived",
            source=rel_source,
            archive=rel_archive,
            manifest=rel_manifest,
            closed_rows=int(manifest_payload["closed_rows"]),
            closed_by=tuple(str(ref) for ref in manifest_payload["closed_by"]),
            sha256=str(manifest_payload["sha256"]),
        )

    if not source_exists:
        return _plan(
            project_root,
            dag,
            status="blocked",
            source=rel_source,
            archive=rel_archive,
            manifest=rel_manifest,
            blockers=("retired-edge-file-missing",),
        )

    migration_plan = build_retired_edge_migration_plan(project_root, dag=dag)
    counts = Counter(row.status for row in migration_plan.rows)
    if not migration_plan.rows:
        return _plan(
            project_root,
            dag,
            status="blocked",
            source=rel_source,
            archive=rel_archive,
            manifest=rel_manifest,
            blockers=("empty-retired-edge-file",),
            row_status_counts=dict(counts),
            sha256=_sha256_file(source),
        )

    if counts != {"closed": len(migration_plan.rows)}:
        return _plan(
            project_root,
            dag,
            status="blocked",
            source=rel_source,
            archive=rel_archive,
            manifest=rel_manifest,
            blockers=("not-all-retired-edge-rows-closed",),
            row_status_counts=dict(counts),
            sha256=_sha256_file(source),
        )

    closed_by = tuple(closed_id for row in migration_plan.rows for closed_id in row.closed_by)
    return _plan(
        project_root,
        dag,
        status="ready_to_archive",
        source=rel_source,
        archive=rel_archive,
        manifest=rel_manifest,
        closed_rows=len(migration_plan.rows),
        closed_by=closed_by,
        row_status_counts=dict(counts),
        sha256=_sha256_file(source),
    )


def _plan(
    project_root: Path,
    dag: str,
    *,
    status: RetiredEdgeArchiveStatus,
    source: str,
    archive: str,
    manifest: str,
    closed_rows: int = 0,
    closed_by: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    row_status_counts: dict[str, int] | None = None,
    sha256: str | None = None,
    applied: bool = False,
) -> RetiredEdgeArchivePlan:
    return RetiredEdgeArchivePlan(
        project_root=project_root.as_posix(),
        dag=dag,
        status=status,
        source=source,
        archive=archive,
        manifest=manifest,
        closed_rows=closed_rows,
        closed_by=closed_by,
        blockers=blockers,
        row_status_counts=row_status_counts or {},
        sha256=sha256,
        applied=applied,
    )


def _paths(project_root: Path, dag: str) -> tuple[Path, Path, Path]:
    if not dag.strip():
        raise ValueError("--dag is required")
    dag_dir = load_dag_paths(project_root).dag_dir
    source = dag_dir / f"{dag}.edges.yaml"
    archive = project_root / ARCHIVE_DIR / f"{dag}.edges.yaml"
    manifest = archive.with_name(f"{archive.name}.archive.json")
    _assert_within_project(project_root, archive)
    _assert_within_project(project_root, manifest)
    return source, archive, manifest


def _assert_within_project(project_root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"archive path escapes project root: {path}") from exc


def _relative(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def _read_manifest(path: Path, *, dag: str, archive: str, source: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid retired edge archive manifest {path}") from exc
    required = {
        "schema_version",
        "dag",
        "original_path",
        "archived_path",
        "closed_by",
        "closed_rows",
        "sha256",
        "archived_at",
        "tool",
        "reason",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"invalid retired edge archive manifest {path}: missing {sorted(missing)}")
    if payload["schema_version"] != ARCHIVE_SCHEMA_VERSION:
        raise ValueError(f"invalid retired edge archive manifest {path}: schema_version")
    if payload["dag"] != dag or payload["original_path"] != source or payload["archived_path"] != archive:
        raise ValueError(f"invalid retired edge archive manifest {path}: path mismatch")
    if not isinstance(payload["closed_by"], list) or not all(isinstance(ref, str) for ref in payload["closed_by"]):
        raise ValueError(f"invalid retired edge archive manifest {path}: closed_by")
    if not isinstance(payload["closed_rows"], int) or payload["closed_rows"] < 0:
        raise ValueError(f"invalid retired edge archive manifest {path}: closed_rows")
    if not isinstance(payload["sha256"], str) or not payload["sha256"].startswith("sha256:"):
        raise ValueError(f"invalid retired edge archive manifest {path}: sha256")
    return payload
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/dag/test_retired_edge_archive.py -q
```

Expected: PASS for the dry-run tests in Task 1.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
rtk git add src/science_tool/dag/retired_edge_archive.py tests/dag/test_retired_edge_archive.py
rtk git commit -m "feat(dag): plan retired edge file archive"
```

---

### Task 2: Implement Apply, Manifest Writing, and Rollback

**Files:**
- Modify: `science/src/science_tool/dag/retired_edge_archive.py`
- Modify: `science/tests/dag/test_retired_edge_archive.py`

- [ ] **Step 1: Add failing apply tests**

Append to `science/tests/dag/test_retired_edge_archive.py`:

```python
def test_apply_retired_edge_archive_moves_file_and_writes_manifest(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    source = project / "doc/figures/dags/h1.edges.yaml"
    before = source.read_text(encoding="utf-8")

    result = apply_retired_edge_archive(project, dag="h1", now="2026-07-05")
    payload = result.to_json()

    assert payload["status"] == "already_archived"
    assert payload["applied"] is True
    assert not source.exists()
    archived = _archive_path(project)
    manifest = _manifest_path(project)
    assert archived.read_text(encoding="utf-8") == before
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload == {
        "archived_at": "2026-07-05",
        "archived_path": "archive/dag-retired-edges/h1.edges.yaml",
        "closed_by": ["proposition:a-affects-b"],
        "closed_rows": 1,
        "dag": "h1",
        "original_path": "doc/figures/dags/h1.edges.yaml",
        "reason": "all-retired-edges-closed",
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "sha256": payload["sha256"],
        "tool": "science dag archive-retired-edges",
    }


def test_apply_retired_edge_archive_rerun_reports_already_archived(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    first = apply_retired_edge_archive(project, dag="h1", now="2026-07-05").to_json()
    second = apply_retired_edge_archive(project, dag="h1", now="2026-07-06").to_json()

    assert first["status"] == "already_archived"
    assert first["applied"] is True
    assert second["status"] == "already_archived"
    assert second["applied"] is False
    assert second["closed_by"] == ["proposition:a-affects-b"]


def test_apply_retired_edge_archive_refuses_blocked_plan(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)

    with pytest.raises(ValueError, match="not ready to archive"):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert (project / "doc/figures/dags/h1.edges.yaml").exists()
    assert not _archive_path(project).exists()
    assert not _manifest_path(project).exists()


def test_apply_retired_edge_archive_refuses_destination_collision(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    _archive_path(project).parent.mkdir(parents=True)
    _archive_path(project).write_text("collision\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ambiguous_state"):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert (project / "doc/figures/dags/h1.edges.yaml").exists()
    assert _archive_path(project).read_text(encoding="utf-8") == "collision\n"


def test_apply_retired_edge_archive_rolls_back_when_manifest_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import science_tool.dag.retired_edge_archive as module
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)
    source = project / "doc/figures/dags/h1.edges.yaml"
    before = source.read_text(encoding="utf-8")

    def fail_manifest(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(module, "_write_manifest_file", fail_manifest)

    with pytest.raises(OSError, match="disk full"):
        apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    assert source.read_text(encoding="utf-8") == before
    assert not _archive_path(project).exists()
    assert not _manifest_path(project).exists()
```

- [ ] **Step 2: Run apply tests to verify they fail**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/dag/test_retired_edge_archive.py -q
```

Expected: FAIL because `apply_retired_edge_archive` and `_write_manifest_file` do not exist.

- [ ] **Step 3: Implement apply and manifest writing**

Modify `science/src/science_tool/dag/retired_edge_archive.py`:

```python
import os
import shutil
from datetime import date
```

Add below `build_retired_edge_archive_plan(...)`:

```python
def apply_retired_edge_archive(project_root: Path, *, dag: str, now: str | None = None) -> RetiredEdgeArchivePlan:
    project_root = Path(project_root).resolve()
    plan = build_retired_edge_archive_plan(project_root, dag=dag)
    if plan.status == "already_archived":
        return plan
    if plan.status != "ready_to_archive":
        raise ValueError(f"retired edge file {dag!r} is not ready to archive: {plan.status} {list(plan.blockers)}")

    source, archive, manifest = _paths(project_root, dag)
    current_sha = _sha256_file(source)
    if current_sha != plan.sha256:
        raise ValueError(f"retired edge file {plan.source} changed during archive planning")
    if archive.exists() or manifest.exists():
        raise ValueError(f"retired edge file {dag!r} entered ambiguous_state before archive")

    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(archive))
    _fsync_dir(archive.parent)
    try:
        _write_manifest_file(
            manifest,
            dag=dag,
            source=plan.source,
            archive=plan.archive,
            closed_rows=plan.closed_rows,
            closed_by=plan.closed_by,
            sha256=current_sha,
            archived_at=now or date.today().isoformat(),
        )
    except Exception:
        shutil.move(str(archive), str(source))
        _fsync_dir(source.parent)
        raise

    return replace(
        plan,
        status="already_archived",
        applied=True,
        sha256=current_sha,
    )
```

Add helper functions near `_read_manifest(...)`:

```python
def _write_manifest_file(
    path: Path,
    *,
    dag: str,
    source: str,
    archive: str,
    closed_rows: int,
    closed_by: tuple[str, ...],
    sha256: str,
    archived_at: str,
) -> None:
    payload = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "dag": dag,
        "original_path": source,
        "archived_path": archive,
        "closed_by": list(closed_by),
        "closed_rows": closed_rows,
        "sha256": sha256,
        "archived_at": archived_at,
        "tool": ARCHIVE_TOOL,
        "reason": ARCHIVE_REASON,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _fsync_file(path)
    _fsync_dir(path.parent)


def _fsync_file(path: Path) -> None:
    with open(path, "rb") as fh:
        os.fsync(fh.fileno())


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
```

- [ ] **Step 4: Run apply tests**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/dag/test_retired_edge_archive.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
rtk git add src/science_tool/dag/retired_edge_archive.py tests/dag/test_retired_edge_archive.py
rtk git commit -m "feat(dag): apply retired edge file archive"
```

---

### Task 3: Add Table Rendering and CLI Command

**Files:**
- Modify: `science/src/science_tool/dag/retired_edge_archive.py`
- Modify: `science/src/science_tool/dag/cli.py`
- Modify: `science/tests/dag/test_cli.py`
- Modify: `science/tests/test_cli_surface_contract.py`

- [ ] **Step 1: Add CLI tests**

Append near the other retired-edge CLI tests in `science/tests/dag/test_cli.py`:

```python
def test_cli_dag_archive_retired_edges_json_reports_ready(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "archive-retired-edges",
            "--project",
            str(project),
            "--dag",
            "h1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_to_archive"
    assert payload["applied"] is False
    assert payload["closed_rows"] == 1
    assert payload["closed_by"] == ["proposition:a-affects-b"]
    assert payload["source"] == "doc/figures/dags/h1.edges.yaml"
    assert payload["archive"] == "archive/dag-retired-edges/h1.edges.yaml"
    assert (project / "doc/figures/dags/h1.edges.yaml").exists()
    assert not (project / "archive/dag-retired-edges/h1.edges.yaml").exists()


def test_cli_dag_archive_retired_edges_table_reports_ready(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)

    result = CliRunner().invoke(
        main,
        ["dag", "archive-retired-edges", "--project", str(project), "--dag", "h1"],
    )

    assert result.exit_code == 0, result.output
    assert "Retired edge archive plan: h1 ready_to_archive" in result.output
    assert "closed_rows: 1" in result.output
    assert "archive/dag-retired-edges/h1.edges.yaml" in result.output


def test_cli_dag_archive_retired_edges_apply_moves_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "archive-retired-edges",
            "--project",
            str(project),
            "--dag",
            "h1",
            "--apply",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "already_archived"
    assert payload["applied"] is True
    assert not (project / "doc/figures/dags/h1.edges.yaml").exists()
    assert (project / "archive/dag-retired-edges/h1.edges.yaml").exists()
    assert (project / "archive/dag-retired-edges/h1.edges.yaml.archive.json").exists()


def test_cli_dag_archive_retired_edges_apply_rerun_reports_already_archived(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)
    _write_retired_migration_lineage_proposition(project)
    args = [
        "dag",
        "archive-retired-edges",
        "--project",
        str(project),
        "--dag",
        "h1",
        "--apply",
        "--format",
        "json",
    ]

    first = CliRunner().invoke(main, args)
    second = CliRunner().invoke(main, args)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert json.loads(first.stdout)["applied"] is True
    second_payload = json.loads(second.stdout)
    assert second_payload["status"] == "already_archived"
    assert second_payload["applied"] is False


def test_cli_dag_archive_retired_edges_dry_run_reports_blocked_without_failing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        ["dag", "archive-retired-edges", "--project", str(project), "--dag", "h1", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["not-all-retired-edge-rows-closed"]
    assert payload["applied"] is False
    assert (project / "doc/figures/dags/h1.edges.yaml").exists()


def test_cli_dag_archive_retired_edges_apply_blocked_is_click_error(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_retired_migration_project(project)

    result = CliRunner().invoke(
        main,
        ["dag", "archive-retired-edges", "--project", str(project), "--dag", "h1", "--apply"],
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "not ready to archive" in result.output
    assert (project / "doc/figures/dags/h1.edges.yaml").exists()


def test_cli_dag_help_lists_archive_retired_edges() -> None:
    result = CliRunner().invoke(main, ["dag", "--help"])

    assert result.exit_code == 0, result.output
    assert "archive-retired-edges" in result.output
```

- [ ] **Step 2: Update CLI surface-contract tests**

Modify `science/tests/test_cli_surface_contract.py`:

```python
_PROJECT_OPTION_ALLOWLIST: dict[str, tuple[str, str]] = {
    ...
    "dag archive-retired-edges": (
        "DAG retired edge archive write surface; retains --project-root alongside --project",
        "project root",
    ),
    ...
}
```

Add to `_PROJECT_ROOT_ALIAS_COMMANDS`:

```python
"dag archive-retired-edges",
```

- [ ] **Step 3: Run CLI tests to verify failure**

Run:

```bash
cd science
rtk uv run --frozen pytest \
  tests/dag/test_cli.py::test_cli_dag_archive_retired_edges_json_reports_ready \
  tests/dag/test_cli.py::test_cli_dag_help_lists_archive_retired_edges \
  tests/test_cli_surface_contract.py::test_project_option_usage_is_intentionally_classified \
  -q
```

Expected: FAIL because the command is not registered.

- [ ] **Step 4: Add table renderer**

Append to `science/src/science_tool/dag/retired_edge_archive.py`:

```python
def render_retired_edge_archive_table(plan: RetiredEdgeArchivePlan) -> str:
    lines = [f"Retired edge archive plan: {plan.dag} {plan.status}"]
    lines.append(f"  source: {plan.source}")
    lines.append(f"  archive: {plan.archive}")
    lines.append(f"  manifest: {plan.manifest}")
    lines.append(f"  applied: {str(plan.applied).lower()}")
    lines.append(f"  closed_rows: {plan.closed_rows}")
    if plan.closed_by:
        lines.append(f"  closed_by: {', '.join(plan.closed_by)}")
    if plan.blockers:
        lines.append(f"  blockers: {', '.join(plan.blockers)}")
    if plan.row_status_counts:
        counts = ", ".join(f"{key}={value}" for key, value in sorted(plan.row_status_counts.items()))
        lines.append(f"  row_status_counts: {counts}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Wire the CLI command**

In `science/src/science_tool/dag/cli.py`, add the command after `scaffold_retired_edge_workbench_cmd(...)` and before the schema section:

```python
@dag_group.command("archive-retired-edges")
@click.option(
    "--dag",
    "slug",
    required=True,
    help="Retired DAG slug whose closed *.edges.yaml file should be archived.",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    default=False,
    help="Move the retired edge file and write the archive manifest.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def archive_retired_edges_cmd(
    slug: str,
    apply_changes: bool,
    output_format: str,
    project_path: Path | None,
) -> None:
    """Archive a fully closed retired DAG *.edges.yaml file."""
    from science_tool.dag.retired_edge_archive import (
        apply_retired_edge_archive,
        build_retired_edge_archive_plan,
        render_retired_edge_archive_table,
    )

    project = (project_path or Path.cwd()).resolve()
    try:
        result = (
            apply_retired_edge_archive(project, dag=slug)
            if apply_changes
            else build_retired_edge_archive_plan(project, dag=slug)
        )
        if output_format == "json":
            click.echo(json.dumps(result.to_json(), indent=2, sort_keys=True))
            return
        click.echo(render_retired_edge_archive_table(result), nl=False)
    except (FileNotFoundError, KeyError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
```

- [ ] **Step 6: Run CLI tests**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/dag/test_cli.py tests/test_cli_surface_contract.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
rtk git add src/science_tool/dag/retired_edge_archive.py src/science_tool/dag/cli.py tests/dag/test_cli.py tests/test_cli_surface_contract.py
rtk git commit -m "feat(dag): add retired edge archive CLI"
```

---

### Task 4: Pin Archived Files as Invisible to Active Retired-Edge Surfaces

**Files:**
- Modify: `science/tests/dag/test_retired_edge_archive.py`

- [ ] **Step 1: Add regression tests for post-archive surfaces**

Append to `science/tests/dag/test_retired_edge_archive.py`:

```python
def test_archived_retired_edge_file_is_not_active_migration_debt(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive
    from science_tool.dag.retired_edge_migration import build_retired_edge_migration_plan
    from science_tool.dag.retired_edges import build_retired_edges_report

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    retired_report = build_retired_edges_report(project, dag="h1").to_json()
    assert retired_report["summary"]["files"] == 0
    assert retired_report["files"] == []
    with pytest.raises(ValueError, match="retired DAG edge file does not exist"):
        build_retired_edge_migration_plan(project, dag="h1")


def test_archived_retired_edge_file_does_not_break_dag_validation(tmp_path: Path) -> None:
    from science_tool.dag.retired_edge_archive import apply_retired_edge_archive
    from science_tool.dag.validate import validate_project

    project = tmp_path / "project"
    _write_retired_edge_project(project)
    _write_lineage_proposition(project)

    apply_retired_edge_archive(project, dag="h1", now="2026-07-05")

    report = validate_project(project, dag="h1")
    assert report.findings == []
```

- [ ] **Step 2: Run regression tests**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/dag/test_retired_edge_archive.py -q
```

Expected: PASS. These tests should pass with the implementation from Tasks 1-3 because active surfaces already scan only `doc/figures/dags/*.edges.yaml`.

- [ ] **Step 3: Commit Task 4**

Run:

```bash
rtk git add tests/dag/test_retired_edge_archive.py
rtk git commit -m "test(dag): pin retired edge archive invisibility"
```

---

### Task 5: Full Verification in the Toolkit Worktree

**Files:**
- No planned file changes.

- [ ] **Step 1: Run focused pytest suite**

Run:

```bash
cd science
rtk uv run --frozen pytest \
  tests/dag/test_retired_edge_archive.py \
  tests/dag/test_retired_edge_migration.py \
  tests/dag/test_cli.py \
  tests/test_cli_surface_contract.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
cd science
rtk uv run --frozen ruff check \
  src/science_tool/dag/retired_edge_archive.py \
  src/science_tool/dag/cli.py \
  tests/dag/test_retired_edge_archive.py \
  tests/dag/test_cli.py \
  tests/test_cli_surface_contract.py
```

Expected: PASS.

- [ ] **Step 3: Run type checking on the new module and CLI**

Run:

```bash
cd science
rtk uv run --frozen pyright \
  src/science_tool/dag/retired_edge_archive.py \
  src/science_tool/dag/cli.py
```

Expected: PASS.

- [ ] **Step 4: Commit any verification fixes**

If Tasks 5.1-5.3 required edits, commit them:

```bash
rtk git add src/science_tool/dag/retired_edge_archive.py src/science_tool/dag/cli.py tests/dag/test_retired_edge_archive.py tests/dag/test_cli.py tests/test_cli_surface_contract.py
rtk git commit -m "fix(dag): harden retired edge archive surface"
```

If no edits were needed, do not create an empty commit.

---

### Task 6: Protein-Landscape Smoke and Apply

**Files:**
- No toolkit files should change.
- Expected project changes in `~/d/protein-landscape`:
  - Move: `doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml`
  - Create: `archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml.archive.json`

- [ ] **Step 1: Confirm protein-landscape starts clean**

Run:

```bash
rtk git -C ~/d/protein-landscape status --short --branch
```

Expected: clean worktree. If not clean, stop and inspect; do not mix project cleanup with unrelated changes.

- [ ] **Step 2: Dry-run archive from the toolkit worktree**

Run from `science/` in the Phase 5k worktree:

```bash
rtk uv run --frozen science dag archive-retired-edges \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --format json
```

Expected JSON facts:

```json
{
  "status": "ready_to_archive",
  "applied": false,
  "closed_rows": 6,
  "source": "doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml",
  "archive": "archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml"
}
```

Also inspect that `closed_by` lists the six migrated propositions:

- `proposition:snapshots-affects-pc1`
- `proposition:lenses-affects-orthogonality`
- `proposition:pc1-affects-residualization`
- `proposition:residualization-affects-coherence`
- `proposition:orthogonality-affects-interaction`
- `proposition:interaction-affects-robust`

- [ ] **Step 3: Apply archive to protein-landscape**

Run from `science/` in the Phase 5k worktree:

```bash
rtk uv run --frozen science dag archive-retired-edges \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --apply \
  --format json
```

Expected JSON facts:

```json
{
  "status": "already_archived",
  "applied": true,
  "closed_rows": 6
}
```

- [ ] **Step 4: Verify file movement**

Run:

```bash
rtk git -C ~/d/protein-landscape status --short
```

Expected:

```text
D  doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml
?? archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml
?? archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml.archive.json
```

If git detects a rename instead of delete/add, that is acceptable. Do not force a specific rename display.

- [ ] **Step 5: Re-run apply to verify idempotency**

Run:

```bash
rtk uv run --frozen science dag archive-retired-edges \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --apply \
  --format json
```

Expected:

```json
{
  "status": "already_archived",
  "applied": false,
  "closed_rows": 6
}
```

- [ ] **Step 6: Verify project-facing DAG behavior**

Run:

```bash
rtk uv run --frozen science dag validate \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe
```

Expected:

```text
dag validate: OK
```

Run:

```bash
rtk uv run --frozen science dag retired-edge-migration-plan \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --format json
```

Expected: non-zero exit with a message containing `retired DAG edge file does not exist`.

Run:

```bash
rtk uv run --frozen science dag retired-edges \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --format json
```

Expected JSON summary:

```json
{
  "files": 0,
  "edges": 0
}
```

- [ ] **Step 7: Commit protein-landscape change directly in that repo**

Run:

```bash
rtk git -C ~/d/protein-landscape add \
  doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml \
  archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml \
  archive/dag-retired-edges/h01-multi-manifold-protein-universe.edges.yaml.archive.json
rtk git -C ~/d/protein-landscape commit -m "chore(dag): archive migrated retired edges"
```

Expected: commit succeeds. Do not include toolkit changes in this project commit.

- [ ] **Step 8: Commit smoke-observation doc only if needed**

If the protein-landscape smoke exposes a noteworthy behavior that the design did not predict, add a short note under `docs/plans/` in the toolkit worktree and commit it. If the smoke follows the expected behavior, skip this step.

---

### Task 7: Final Verification and Review Prep

**Files:**
- No planned file changes unless verification uncovers issues.

- [ ] **Step 1: Re-run focused toolkit verification**

Run:

```bash
cd science
rtk uv run --frozen pytest \
  tests/dag/test_retired_edge_archive.py \
  tests/dag/test_retired_edge_migration.py \
  tests/dag/test_cli.py \
  tests/test_cli_surface_contract.py \
  -q
rtk uv run --frozen ruff check \
  src/science_tool/dag/retired_edge_archive.py \
  src/science_tool/dag/cli.py \
  tests/dag/test_retired_edge_archive.py \
  tests/dag/test_cli.py \
  tests/test_cli_surface_contract.py
rtk uv run --frozen pyright \
  src/science_tool/dag/retired_edge_archive.py \
  src/science_tool/dag/cli.py
```

Expected: all commands PASS.

- [ ] **Step 2: Review git status in both repositories**

Run:

```bash
rtk git status --short --branch
rtk git -C ~/d/protein-landscape status --short --branch
```

Expected:

- toolkit worktree clean after committing all implementation changes;
- protein-landscape clean after its project commit.

- [ ] **Step 3: Request code review**

Use `superpowers:requesting-code-review`. Ask reviewers to focus on:

- partial-state classification (`already_archived` vs `ambiguous_state`);
- apply rollback and overwrite refusal;
- whether dry-run blocked status should remain exit 0;
- archived retired file invisibility to active migration surfaces;
- protein-landscape apply result.

- [ ] **Step 4: Address review findings**

If review finds issues, use `superpowers:receiving-code-review` before editing. Add focused tests for each accepted finding, implement the fix, rerun Task 7.1, and commit with a precise message.

- [ ] **Step 5: Prepare merge**

Use `superpowers:finishing-a-development-branch`. The likely path is:

```bash
rtk git switch main
rtk git merge --no-ff phase5k-retired-edge-archive
```

Do not remove the worktree until the merge and final status checks are complete.

## Acceptance Checklist

- [ ] `science dag archive-retired-edges --dag <slug>` reports `ready_to_archive` only when every retired row is `closed`.
- [ ] Non-closed retired files block archive and are not moved.
- [ ] Apply moves the active retired file to `archive/dag-retired-edges/`.
- [ ] Apply writes a manifest with project-relative paths, `closed_by`, `closed_rows`, SHA-256, timestamp, tool, and reason.
- [ ] Apply never overwrites destination files or manifests.
- [ ] Manifest-write failure restores the source file.
- [ ] Re-run after success reports `already_archived`.
- [ ] Source/archive coexistence and archive/manifest mismatch report `ambiguous_state`.
- [ ] `retired-edges` and `retired-edge-migration-plan` do not scan archived retired files by default.
- [ ] `dag validate` remains OK for protein-landscape after H01 retired edge archive.
- [ ] Protein-landscape H01 retired edge file is archived and committed directly in `~/d/protein-landscape`.

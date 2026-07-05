"""Archive closed retired DAG ``*.edges.yaml`` files.

This module is intentionally narrower than the entity archive. Retired edge
files are source artifacts, not entity records, so they get a project artifact
archive path plus a small manifest.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
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
            manifest_payload = _read_manifest(
                manifest,
                dag=dag,
                archive=rel_archive,
                source=rel_source,
                archived_file=archive,
            )
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


def _read_manifest(path: Path, *, dag: str, archive: str, source: str, archived_file: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid retired edge archive manifest {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid retired edge archive manifest {path}: expected object")
    expected_keys = {
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
    missing = expected_keys - set(payload)
    if missing:
        raise ValueError(f"invalid retired edge archive manifest {path}: missing {sorted(missing)}")
    extra = set(payload) - expected_keys
    if extra:
        raise ValueError(f"invalid retired edge archive manifest {path}: unexpected {sorted(extra)}")
    if payload["schema_version"] != ARCHIVE_SCHEMA_VERSION:
        raise ValueError(f"invalid retired edge archive manifest {path}: schema_version")
    if payload["dag"] != dag or payload["original_path"] != source or payload["archived_path"] != archive:
        raise ValueError(f"invalid retired edge archive manifest {path}: path mismatch")
    if payload["tool"] != ARCHIVE_TOOL:
        raise ValueError(f"invalid retired edge archive manifest {path}: tool")
    if payload["reason"] != ARCHIVE_REASON:
        raise ValueError(f"invalid retired edge archive manifest {path}: reason")
    if not isinstance(payload["archived_at"], str) or not payload["archived_at"].strip():
        raise ValueError(f"invalid retired edge archive manifest {path}: archived_at")
    if not isinstance(payload["closed_by"], list) or not all(isinstance(ref, str) for ref in payload["closed_by"]):
        raise ValueError(f"invalid retired edge archive manifest {path}: closed_by")
    if not isinstance(payload["closed_rows"], int) or payload["closed_rows"] < 0:
        raise ValueError(f"invalid retired edge archive manifest {path}: closed_rows")
    if not isinstance(payload["sha256"], str) or not payload["sha256"].startswith("sha256:"):
        raise ValueError(f"invalid retired edge archive manifest {path}: sha256")
    if payload["sha256"] != _sha256_file(archived_file):
        raise ValueError(f"invalid retired edge archive manifest {path}: sha256 mismatch")
    return payload

"""Explicit inspection surface for retired ``*.edges.yaml`` files.

Default DAG commands must not import this module for semantic edges. This module
exists only to size migration debt and expose remaining retired curation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from science_tool.dag.proposition_edges import load_proposition_edges


_CLAIM_TEXT_KEYS = ("interpretation", "finding", "claim", "description")
_SUPPORT_REF_KEYS = ("data_support", "lit_support", "eliminated_by")


@dataclass(frozen=True)
class RetiredEdgeRow:
    dag: str
    edge_id: str | None
    source: str
    target: str
    edge_status: str | None
    has_claim_text: bool
    support_ref_count: int
    has_matching_proposition: bool

    @property
    def migration_worthy(self) -> bool:
        return (self.has_claim_text or self.support_ref_count > 0) and not self.has_matching_proposition

    def to_json(self) -> dict[str, Any]:
        return {
            "dag": self.dag,
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "edge_status": self.edge_status,
            "has_claim_text": self.has_claim_text,
            "support_ref_count": self.support_ref_count,
            "has_matching_proposition": self.has_matching_proposition,
            "migration_worthy": self.migration_worthy,
        }


@dataclass(frozen=True)
class RetiredEdgesFileReport:
    path: str
    dag: str
    dot_path: str | None
    orphan_dot: bool
    edges: tuple[RetiredEdgeRow, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        status_counts = Counter(row.edge_status or "<missing>" for row in self.edges)
        return {
            "path": self.path,
            "dag": self.dag,
            "dot_path": self.dot_path,
            "orphan_dot": self.orphan_dot,
            "edge_count": len(self.edges),
            "edge_status_counts": dict(sorted(status_counts.items())),
            "edges": [row.to_json() for row in self.edges],
        }


@dataclass(frozen=True)
class RetiredEdgesReport:
    project_root: str
    files: tuple[RetiredEdgesFileReport, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        rows = [row for file in self.files for row in file.edges]
        summary = {
            "files": len(self.files),
            "edges": len(rows),
            "orphan_files": sum(1 for file in self.files if file.orphan_dot),
            "claim_text_edges": sum(1 for row in rows if row.has_claim_text),
            "support_ref_edges": sum(1 for row in rows if row.support_ref_count > 0),
            "migration_worthy_edges": sum(1 for row in rows if row.migration_worthy),
        }
        return {
            "project_root": self.project_root,
            "summary": summary,
            "files": [file.to_json() for file in self.files],
        }


def build_retired_edges_report(project_root: Path, *, dag: str | None = None) -> RetiredEdgesReport:
    dag_dir = project_root / "doc/figures/dags"
    yaml_paths = [dag_dir / f"{dag}.edges.yaml"] if dag else sorted(dag_dir.glob("*.edges.yaml"))
    proposition_pairs = {
        (str(edge.get("source", "")), str(edge.get("target", ""))) for edge in load_proposition_edges(project_root)
    }

    files: list[RetiredEdgesFileReport] = []
    for yaml_path in yaml_paths:
        if not yaml_path.exists():
            continue
        payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            payload = {}
        dag_slug = str(payload.get("dag") or yaml_path.name.removesuffix(".edges.yaml"))
        dot_path = _resolve_dot_path(project_root, yaml_path, payload, dag_slug)
        edges = tuple(
            _edge_row(dag_slug, edge, proposition_pairs) for edge in payload.get("edges") or [] if isinstance(edge, dict)
        )
        files.append(
            RetiredEdgesFileReport(
                path=yaml_path.relative_to(project_root).as_posix(),
                dag=dag_slug,
                dot_path=dot_path.relative_to(project_root).as_posix() if dot_path and dot_path.exists() else None,
                orphan_dot=not bool(dot_path and dot_path.exists()),
                edges=edges,
            )
        )

    return RetiredEdgesReport(project_root=project_root.as_posix(), files=tuple(files))


def _resolve_dot_path(project_root: Path, yaml_path: Path, payload: dict[str, Any], dag_slug: str) -> Path | None:
    source_dot = payload.get("source_dot")
    if isinstance(source_dot, str) and source_dot.strip():
        candidate = project_root / source_dot
        return candidate if candidate.exists() else yaml_path.parent / source_dot
    return yaml_path.parent / f"{dag_slug}.dot"


def _edge_row(
    dag: str,
    edge: dict[str, Any],
    proposition_pairs: set[tuple[str, str]],
) -> RetiredEdgeRow:
    source = str(edge.get("source") or "")
    target = str(edge.get("target") or "")
    support_count = 0
    for key in _SUPPORT_REF_KEYS:
        value = edge.get(key)
        if isinstance(value, list):
            support_count += len(value)
    has_claim_text = any(isinstance(edge.get(key), str) and edge[key].strip() for key in _CLAIM_TEXT_KEYS)
    edge_id = edge.get("id")
    return RetiredEdgeRow(
        dag=dag,
        edge_id=str(edge_id).strip() if edge_id is not None else None,
        source=source,
        target=target,
        edge_status=str(edge.get("edge_status")).strip() if edge.get("edge_status") is not None else None,
        has_claim_text=has_claim_text,
        support_ref_count=support_count,
        has_matching_proposition=(source, target) in proposition_pairs,
    )

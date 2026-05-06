"""Federation validation: meta children manifest vs. child parent back-references."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_tool.project_config import (
    ChildEntry,
    ProjectRole,
    load_project_config,
    paths_equivalent,
    resolve_child_path,
    resolve_parent_path,
)

IssueKind = Literal[
    "child_path_missing",
    "missing_parent",
    "parent_mismatch",
    "role_mismatch",
    "id_mismatch",
]


@dataclass(frozen=True)
class FederationIssue:
    kind: IssueKind
    child_id: str | None
    detail: str


def validate_federation(meta_root: Path) -> list[FederationIssue]:
    """Validate meta's children manifest against each child's parent back-reference."""
    meta_cfg = load_project_config(meta_root)
    if meta_cfg.role != ProjectRole.META:
        raise ValueError(f"{meta_root} is role={meta_cfg.role!r}; not a meta project")

    issues: list[FederationIssue] = []
    meta_resolved = meta_root.resolve()
    for child in meta_cfg.children:
        issues.extend(_validate_one_child(child, meta_resolved))
    return issues


def _validate_one_child(child: ChildEntry, meta_resolved: Path) -> list[FederationIssue]:
    issues: list[FederationIssue] = []
    child_path = resolve_child_path(child)

    if not child_path.is_dir() or not (child_path / "science.yaml").is_file():
        return [
            FederationIssue(
                kind="child_path_missing",
                child_id=child.id,
                detail=f"no science.yaml at {child_path}",
            )
        ]

    child_cfg = load_project_config(child_path)

    if child_cfg.id != child.id:
        issues.append(
            FederationIssue(
                kind="id_mismatch",
                child_id=child.id,
                detail=f"manifest says id={child.id!r}, child science.yaml says id={child_cfg.id!r}",
            )
        )

    if child_cfg.role != child.role:
        issues.append(
            FederationIssue(
                kind="role_mismatch",
                child_id=child.id,
                detail=f"manifest says role={child.role!r}, child says role={child_cfg.role!r}",
            )
        )

    if child_cfg.parent is None:
        issues.append(
            FederationIssue(
                kind="missing_parent",
                child_id=child.id,
                detail="child science.yaml has no parent: declared",
            )
        )
        return issues

    resolved_parent = resolve_parent_path(child_cfg.parent)
    if resolved_parent is None or not paths_equivalent(resolved_parent, meta_resolved):
        issues.append(
            FederationIssue(
                kind="parent_mismatch",
                child_id=child.id,
                detail=f"child parent={child_cfg.parent!r} resolves to {resolved_parent}, expected {meta_resolved}",
            )
        )

    return issues

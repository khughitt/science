"""Promote paper entities from per-project files into the commons store.

Pipeline: discover → plan → apply. Atomic-batch transaction semantics
per docs/plans/2026-05-15-commons-promote-papers-design.md §6.3.

This module owns:
- Dataclasses for the public surface (PromoteCandidate, PromotePlan, …).
- `discover_paper_candidates(project_slugs) -> DiscoveryResult` (Task 10).
- `plan_promote(discovery, commons_root, *, resolve_conflict) -> PromotePlan` (Task 14).
- `apply_promote(plan, commons_root, *, invocation) -> PromoteResult` (Tasks 16–17).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal


# --------------------------------------------------------------------------- #
# Public dataclasses                                                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PromoteCandidate:
    """One paper file found during discovery.

    `bibkey` is the source's case (filename stem). `bibkey_normalized` is
    casefold() used only for dedup grouping. See design §4.1.3.
    """

    bibkey: str
    bibkey_normalized: str
    project_slug: str
    project_root: Path
    overlay_source_path: Path
    canonical_fields: dict[str, Any]
    project_only_fields: dict[str, Any]
    canonical_body: dict[str, str]
    project_only_body: dict[str, Any]
    # `project_only_body` is `dict[str, Any]` (not `[str, str]`) so the
    # discovery phase can stash the raw `(frontmatter, body)` pair under
    # sentinel keys `__raw_frontmatter__` / `__raw_body__` for `plan_promote`
    # to consume during classification. After `_classify_entity` runs in
    # `plan_promote`, the dict's values are pure `str` again.


@dataclass(frozen=True, slots=True)
class FieldConflict:
    bibkey: str
    field: str
    candidates: dict[str, Any]  # project_slug → value


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    bibkey: str
    field: str
    candidates: dict[str, Any]
    resolved_to: Any
    source_project: str | None  # None if user entered a manual value


@dataclass(frozen=True, slots=True)
class OverlayRewrite:
    project_slug: str
    path: Path
    before_sha: str
    after_content: str
    pin_version: str
    rename_from: Path | None = None  # set when canonical case differs from source


@dataclass(frozen=True, slots=True)
class PromoteDecision:
    bibkey: str
    canonical_path: Path                 # absolute `<commons>/papers/<bibkey>.md`
    canonical_content: str               # rendered canonical file (markdown + frontmatter)
    canonical_version: str               # "1.0.0" etc.
    overlays: dict[str, OverlayRewrite]  # project_slug → rewrite plan
    resolved_conflicts: tuple[ConflictResolution, ...]


@dataclass(frozen=True, slots=True)
class FailedCandidate:
    bibkey: str | None
    project_slug: str
    source_path: Path
    error_class: str
    error_message: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates_by_bibkey: dict[str, list[PromoteCandidate]]
    failed_candidates: list[FailedCandidate]


@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]


@dataclass(frozen=True, slots=True)
class PromoteResult:
    op_id: str
    started_at: datetime
    finished_at: datetime
    commons_commit: str | None
    tags_created: list[str]
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    audit_log_path: Path | None
    status: Literal["ok", "failed"]
    failure_stage: Literal[
        "preflight", "validate", "discover", "plan",
        "write_commons", "rewrite_projects", "audit",
    ] | None
    failure_detail: str | None
    # Project slugs whose `doc/papers/<file>.md` were actually modified by this
    # operation. On the success path, every overlay slug; on a partial step-6
    # failure, just the slugs reached before the failure; on
    # preflight/tag/commit failures (no project file touched), the empty list.
    # The audit log filters `projects_touched` (overlay_rewrites + rollback
    # hints) by this list so failure logs don't suggest rollbacks for projects
    # that were never modified (design §6.3 step 7 failure variant).
    projects_touched: list[str]


# --------------------------------------------------------------------------- #
# Public entry points (stubs — implemented in Tasks 10, 14, 16, 17)           #
# --------------------------------------------------------------------------- #


def discover_paper_candidates(project_slugs: list[str]) -> DiscoveryResult:
    raise NotImplementedError  # Task 10


def plan_promote(
    discovery: DiscoveryResult,
    commons_root: Path,
    *,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
) -> PromotePlan:
    raise NotImplementedError  # Task 14


def apply_promote(
    plan: PromotePlan,
    commons_root: Path,
    *,
    invocation: str,
) -> PromoteResult:
    raise NotImplementedError  # Tasks 16–17

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

import logging
import re
import secrets
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

import click
import yaml

from science_model.entity_schema import (
    MergePolicy,
    ProfileString,
    default_profile_for_kind,
    read_canonical_body_sections,
    read_merge_policy,
)
from science_tool.commons.config import resolve_project_by_id
from science_tool.commons.errors import PromoteCandidateError, PromoteConflictAbort, PromoteInputError, PromoteWriteError


class EligibilityVerdict(Enum):
    ELIGIBLE = "eligible"
    SKIP_SILENT = "skip_silent"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    """Per-kind configuration for the promote pipeline.

    One instance per kind ("paper", "topic", "theme"). Pure data plus an
    optional eligibility-filter callable; threaded through discovery /
    plan / apply via the `kind` parameter or `PromotePlan.kind`.
    """

    kind: Literal["paper", "topic", "theme"]
    source_subdirs: tuple[str, ...]
    overlay_dest_subdir: str
    commons_subdir: str
    id_prefix: str
    slug_regex: re.Pattern[str]
    slug_match: Literal["casefold", "exact"]
    mixin_schema_id: str
    default_profile: "ProfileString"
    eligibility_filter: Callable[[Mapping[str, Any]], "EligibilityVerdict"] | None


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
    """Scan each project's `doc/papers/*.md` directly. Group by case-insensitive
    `bibkey_normalized`. Returns successful candidates + failure records."""
    grouped: dict[str, list[PromoteCandidate]] = {}
    failures: list[FailedCandidate] = []

    for slug in project_slugs:
        project_root = resolve_project_by_id(slug)  # raises CommonsError on bad slug
        candidates, project_failures = _scan_project_papers(project_root, slug)
        failures.extend(project_failures)
        for cand in candidates:
            grouped.setdefault(cand.bibkey_normalized, []).append(cand)

    return DiscoveryResult(candidates_by_bibkey=grouped, failed_candidates=failures)


def prompt_resolve(conflict: FieldConflict) -> Any:
    """Interactive terminal prompt — the default `resolve_conflict` callback.

    UI mirrors design §7.1. Returns the resolved value (a candidate value, a
    user-entered manual value, or raises `PromoteConflictAbort` on 'a' / Ctrl-C).
    """
    click.echo(f'\nConflict for paper:{conflict.bibkey}, field "{conflict.field}":')
    ordered = sorted(conflict.candidates.items())
    for idx, (slug, value) in enumerate(ordered, start=1):
        click.echo(f"  [{idx}] {slug}: {value!r}")
    click.echo(f"  [{len(ordered) + 1}] enter value manually")
    click.echo("  [a] abort batch")
    while True:
        try:
            choice = click.prompt(
                f"Choose [1-{len(ordered) + 1}/a]",
                type=str,
                show_default=False,
            ).strip()
        except (click.Abort, KeyboardInterrupt) as exc:
            raise PromoteConflictAbort("user aborted at conflict prompt") from exc
        if choice.lower() == "a":
            raise PromoteConflictAbort("user chose 'abort batch' at conflict prompt")
        try:
            n = int(choice)
        except ValueError:
            click.echo("invalid selection")
            continue
        if 1 <= n <= len(ordered):
            return ordered[n - 1][1]
        if n == len(ordered) + 1:
            return click.prompt("Manual value", type=str)
        click.echo("out of range")


def plan_promote(
    discovery: DiscoveryResult,
    commons_root: Path,
    *,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
    from_order: list[str] | None = None,
) -> PromotePlan:
    """Build a PromotePlan from a DiscoveryResult.

    For each bibkey group:
      1. Run `_classify_entity` per candidate (consumes the raw frontmatter/body
         stashed by discovery in `project_only_body.__raw_*__`).
      2. Pick canonical bibkey case via `_pick_canonical_bibkey_case`.
      3. Merge canonical fields → `(merged_fields, conflicts)`.
      4. Resolve each conflict via `resolve_conflict`.
      5. Build PromoteDecision (canonical_content rendered, overlays planned).

    `from_order` defaults to the discovery's project_slug encounter order.
    `resolve_conflict` defaults to `prompt_resolve`.
    """
    if resolve_conflict is None:
        resolve_conflict = prompt_resolve

    paper_profile = default_profile_for_kind("paper")
    merge_policy = read_merge_policy(paper_profile)
    body_sections = read_canonical_body_sections(paper_profile)

    if from_order is None:
        from_order = []
        seen_slugs: set[str] = set()
        for cands in discovery.candidates_by_bibkey.values():
            for c in cands:
                if c.project_slug not in seen_slugs:
                    from_order.append(c.project_slug)
                    seen_slugs.add(c.project_slug)

    decisions: list[PromoteDecision] = []
    soft_failures: list[FailedCandidate] = list(discovery.failed_candidates)

    for bibkey_norm in sorted(discovery.candidates_by_bibkey):
        raw_group = discovery.candidates_by_bibkey[bibkey_norm]

        classified: list[PromoteCandidate] = []
        for c in raw_group:
            raw_fm = c.project_only_body.get(_RAW_FRONTMATTER_KEY)
            raw_body = c.project_only_body.get(_RAW_BODY_KEY, "")
            if not isinstance(raw_fm, dict):
                soft_failures.append(
                    FailedCandidate(
                        bibkey=c.bibkey, project_slug=c.project_slug,
                        source_path=c.overlay_source_path,
                        error_class="PromoteCandidateError",
                        error_message="discovery payload missing raw frontmatter",
                    )
                )
                continue
            can_f, proj_f, can_b, proj_b = _classify_entity(
                raw_fm, raw_body, merge_policy, body_sections,
            )
            classified.append(
                PromoteCandidate(
                    bibkey=c.bibkey,
                    bibkey_normalized=c.bibkey_normalized,
                    project_slug=c.project_slug,
                    project_root=c.project_root,
                    overlay_source_path=c.overlay_source_path,
                    canonical_fields=can_f,
                    project_only_fields=proj_f,
                    canonical_body=can_b,
                    project_only_body=proj_b,
                )
            )

        if not classified:
            continue

        canonical_case = _pick_canonical_bibkey_case(classified, from_order)

        # Pre-check for case-rename collisions before any conflict prompts
        # (design §4.1.3): if the rename target already exists in the project
        # directory and is NOT the source file itself, the group is un-promotable.
        for c in classified:
            source_path = c.overlay_source_path
            target_path = source_path.parent / f"{canonical_case}.md"
            if source_path.name != target_path.name and target_path.exists():
                raise PromoteInputError(
                    f"case-rename collision in {c.project_slug}: cannot rename "
                    f"{source_path} → {target_path}; target already exists"
                )

        merged, conflicts = _merge_canonical_fields(classified, merge_policy)

        resolved_conflicts: list[ConflictResolution] = []
        for conflict in conflicts:
            resolved_value = resolve_conflict(conflict)
            source_project = next(
                (slug for slug, v in conflict.candidates.items() if v == resolved_value),
                None,
            )
            resolved_conflicts.append(
                ConflictResolution(
                    bibkey=canonical_case,
                    field=conflict.field,
                    candidates=conflict.candidates,
                    resolved_to=resolved_value,
                    source_project=source_project,
                )
            )
            merged[conflict.field] = resolved_value

        canonical_path = commons_root / "papers" / f"{canonical_case}.md"
        overlays: dict[str, OverlayRewrite] = {}
        for c in classified:
            source_path = c.overlay_source_path
            target_path = source_path.parent / f"{canonical_case}.md"
            rename_from = source_path if source_path.name != target_path.name else None
            if rename_from is not None and target_path.exists():
                raise PromoteInputError(
                    f"case-rename collision in {c.project_slug}: cannot rename "
                    f"{rename_from} → {target_path}; target already exists"
                )
            rendered_overlay = _render_overlay(
                PromoteDecision(
                    bibkey=canonical_case,
                    canonical_path=canonical_path,
                    canonical_content="",
                    canonical_version="1.0.0",
                    overlays={},
                    resolved_conflicts=(),
                ),
                project_slug=c.project_slug,
                project_only_fields=c.project_only_fields,
                project_only_body=c.project_only_body,
            )
            overlays[c.project_slug] = OverlayRewrite(
                project_slug=c.project_slug,
                path=target_path,
                before_sha="",
                after_content=rendered_overlay,
                pin_version="1.0.0",
                rename_from=rename_from,
            )

        canonical_decision = PromoteDecision(
            bibkey=canonical_case,
            canonical_path=canonical_path,
            canonical_content="",
            canonical_version="1.0.0",
            overlays=overlays,
            resolved_conflicts=tuple(resolved_conflicts),
        )
        # NOTE: design §4.1.1 says `created` / `updated` should reflect the
        # apply timestamp, not the plan timestamp. We render here with
        # plan-day dates so the dry-run summary can show concrete content;
        # apply_promote (Task 16) re-renders with the actual write-time
        # timestamp before committing. The pre-render is informational only.
        canonical_content = _render_canonical(
            canonical_decision,
            canonical_fields=merged,
            canonical_body=classified[0].canonical_body,
            created=date.today(),
            updated=date.today(),
        )
        decisions.append(
            PromoteDecision(
                bibkey=canonical_case,
                canonical_path=canonical_path,
                canonical_content=canonical_content,
                canonical_version="1.0.0",
                overlays=overlays,
                resolved_conflicts=tuple(resolved_conflicts),
            )
        )

    return PromotePlan(decisions=decisions, failed_candidates=soft_failures)


def _commons_is_clean(commons_root: Path) -> tuple[bool, list[str]]:
    """Return (clean, dirty_paths). Clean = no staged, no unstaged, no untracked
    inside papers/ or .migrations/."""
    status = _git(commons_root, "status", "--porcelain").stdout
    dirty: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        flags = line[:2]
        if flags == "??":
            if path.startswith("papers/") or path.startswith(".migrations/"):
                dirty.append(path)
        else:
            dirty.append(path)
    return (not dirty, dirty)


def _project_target_files_clean(
    project_root: Path, target_filenames: list[str]
) -> tuple[bool, list[str]]:
    """For each filename in `target_filenames`, check whether `doc/papers/<name>`
    matches HEAD. Returns (clean, dirty_paths)."""
    dirty: list[str] = []
    for name in target_filenames:
        rel = f"doc/papers/{name}"
        absolute = project_root / rel
        if not absolute.exists():
            continue
        diff = subprocess.run(
            ["git", "-C", str(project_root), "diff", "--exit-code", "--quiet", "HEAD", "--", rel],
        )
        if diff.returncode != 0:
            dirty.append(rel)
    return (not dirty, dirty)


def _repo_is_idle(root: Path) -> bool:
    """True if the repo is NOT mid-merge/rebase/cherry-pick/bisect."""
    git_dir = root / ".git"
    sentinels = [
        "MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD",
        "BISECT_LOG", "rebase-apply", "rebase-merge",
    ]
    return not any((git_dir / s).exists() for s in sentinels)


def _write_failure_audit_log(
    *,
    op_id: str,
    started_at: datetime,
    commons_root: Path,
    commons_commit: str | None,
    tags_created: list[str],
    plan: PromotePlan,
    projects_touched: list[str],
    failure_stage: Literal[
        "preflight", "validate", "discover", "plan",
        "write_commons", "rewrite_projects", "audit",
    ],
    failure_detail: str,
    invocation: str,
) -> tuple[Path | None, str]:
    """Best-effort uncommitted audit log for a failure path (design §6.3 step 7
    failure variant). Returns `(path, yaml_text)`:
      - On successful write: `(path, yaml_text)` where path is the file written.
      - On write failure: `(None, yaml_text)` — caller is responsible for
        surfacing yaml_text to stderr so the operator can recover forensics
        when the audit dir itself is unwritable."""
    finished_at = datetime.now(tz=timezone.utc)
    result = PromoteResult(
        op_id=op_id,
        started_at=started_at,
        finished_at=finished_at,
        commons_commit=commons_commit,
        tags_created=tags_created,
        decisions=plan.decisions,
        failed_candidates=plan.failed_candidates,
        audit_log_path=None,
        status="failed",
        failure_stage=failure_stage,
        failure_detail=failure_detail,
        projects_touched=projects_touched,
    )
    yaml_text = _render_audit_log_yaml(result, commons_root, invocation=invocation)
    try:
        migrations = commons_root / ".migrations"
        migrations.mkdir(parents=True, exist_ok=True)
        stamp = result.started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = migrations / f"{stamp}-{result.op_id}.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        return (path, yaml_text)
    except OSError as audit_exc:
        logger.error(
            "failure-path audit log write failed for op %s: %s", op_id, audit_exc
        )
        return (None, yaml_text)


def _restore_paths_to_head(commons_root: Path, paths: list[Path]) -> None:
    """For each path, checkout HEAD -- <rel> if it existed at HEAD, else unlink.
    Used in the 'before step 5' failure path."""
    for path in paths:
        rel = path.relative_to(commons_root)
        existed = _git(commons_root, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0
        if existed:
            _git(commons_root, "checkout", "HEAD", "--", str(rel))
        else:
            path.unlink(missing_ok=True)


def apply_promote(
    plan: PromotePlan,
    commons_root: Path,
    *,
    invocation: str,
) -> PromoteResult:
    """Atomic-batch apply per design §6.3.

    The body is wrapped in a try/except that writes a best-effort uncommitted
    audit log on any failure (design §6.3 step 7 failure variant) before
    re-raising. The success path commits the audit log path-limited.
    """
    started_at = datetime.now(tz=timezone.utc)
    op_id = secrets.token_hex(4)
    commons_commit: str | None = None
    tags_created: list[str] = []
    projects_touched: list[str] = []
    current_stage: str = "preflight"

    if not plan.decisions:
        finished_at = datetime.now(tz=timezone.utc)
        return PromoteResult(
            op_id=op_id,
            started_at=started_at,
            finished_at=finished_at,
            commons_commit=None,
            tags_created=[],
            decisions=[],
            failed_candidates=plan.failed_candidates,
            audit_log_path=None,
            status="ok",
            failure_stage=None,
            failure_detail=None,
            projects_touched=[],
        )

    try:
        # ---------- Step 0: preflight ----------
        if not commons_root.exists():
            raise PromoteInputError(
                f"commons store missing at {commons_root}; run `science commons init`"
            )
        if not _repo_is_idle(commons_root):
            raise PromoteInputError(f"commons repo is mid-merge/rebase: {commons_root}")
        clean, dirty = _commons_is_clean(commons_root)
        if not clean:
            raise PromoteInputError(
                "commons repo is not clean. Commit/stash before re-running. Dirty: "
                + ", ".join(dirty)
            )

        target_files_per_project: dict[Path, list[str]] = {}
        rename_collisions: list[tuple[str, Path]] = []
        for decision in plan.decisions:
            for slug, overlay in decision.overlays.items():
                project_root = overlay.path.parent.parent.parent
                if overlay.rename_from is not None:
                    target_files_per_project.setdefault(project_root, []).append(
                        overlay.rename_from.name
                    )
                    if overlay.path.exists():
                        rename_collisions.append((slug, overlay.path))
                else:
                    target_files_per_project.setdefault(project_root, []).append(
                        overlay.path.name
                    )
        if rename_collisions:
            raise PromoteInputError(
                "case-rename target(s) already exist on disk: "
                + ", ".join(f"{slug}:{path}" for slug, path in rename_collisions)
            )

        for project_root, names in target_files_per_project.items():
            if not _repo_is_idle(project_root):
                raise PromoteInputError(f"project {project_root} is mid-merge/rebase")
            clean, dirty = _project_target_files_clean(project_root, names)
            if not clean:
                raise PromoteInputError(
                    f"project {project_root} has dirty target files: " + ", ".join(dirty)
                )

        # ---------- Step 5.1: tag preflight ----------
        current_stage = "write_commons"
        for decision in plan.decisions:
            tag = f"paper/{decision.bibkey}/{decision.canonical_version}"
            existing = _git(commons_root, "rev-parse", "--verify", "--quiet", tag, check=False)
            if existing.returncode == 0:
                raise PromoteWriteError(
                    stage="write_commons",
                    detail=f"tag {tag!r} already exists in commons; refusing to overwrite",
                )

        # ---------- Step 4: write commons (staged) ----------
        # OSError (PermissionError, disk-full) here is recoverable: nothing
        # committed yet, so restore any partially-written canonicals and convert
        # to PromoteWriteError so the outer except writes a failure audit log
        # (design §6.4 "Before step 5" recovery path).
        written_canonical_paths: list[Path] = []
        try:
            for decision in plan.decisions:
                decision.canonical_path.parent.mkdir(parents=True, exist_ok=True)
                decision.canonical_path.write_text(decision.canonical_content, encoding="utf-8")
                written_canonical_paths.append(decision.canonical_path)
        except OSError as exc:
            _restore_paths_to_head(commons_root, written_canonical_paths)
            raise PromoteWriteError(
                stage="write_commons",
                detail=f"commons canonical write failed: {exc}",
            ) from exc

        # ---------- Step 5.2: commit (path-limited) ----------
        rel_paths = [str(p.relative_to(commons_root)) for p in written_canonical_paths]
        try:
            _git(commons_root, "add", "--", *rel_paths)
            _git(
                commons_root,
                "commit", "-m", f"promote: {len(plan.decisions)} papers via op {op_id}",
                "--", *rel_paths,
            )
        except subprocess.CalledProcessError as exc:
            _restore_paths_to_head(commons_root, written_canonical_paths)
            raise PromoteWriteError(
                stage="write_commons",
                detail=f"commons commit failed: {exc.stderr or exc}",
            ) from exc

        commons_commit = _git(commons_root, "rev-parse", "--short", "HEAD").stdout.strip()
        # rev-parse on HEAD after a successful commit is always a non-empty
        # SHA; narrowing here lets the type-checker see commons_commit as `str`
        # for the rest of the function.
        assert commons_commit, "rev-parse HEAD returned empty after commit"

        # ---------- Step 5.3: tag (path-limited per-tag) ----------
        for decision in sorted(plan.decisions, key=lambda d: d.bibkey):
            tag = f"paper/{decision.bibkey}/{decision.canonical_version}"
            try:
                _git(commons_root, "tag", tag, commons_commit)
                tags_created.append(tag)
            except subprocess.CalledProcessError as exc:
                _rollback_step5(commons_root, tags_created, written_canonical_paths)
                rolled_back_commit = commons_commit
                commons_commit = None
                tags_created.clear()
                raise PromoteWriteError(
                    stage="write_commons",
                    detail=(
                        f"tag {tag!r} failed after commit (rolled back "
                        f"{rolled_back_commit}): {exc.stderr or exc}"
                    ),
                ) from exc

        # ---------- Step 6: rewrite projects ----------
        current_stage = "rewrite_projects"
        try:
            for decision in plan.decisions:
                for slug, overlay in decision.overlays.items():
                    if slug not in projects_touched:
                        projects_touched.append(slug)
                    if overlay.rename_from is not None and overlay.rename_from.exists():
                        overlay.rename_from.unlink()
                    overlay.path.parent.mkdir(parents=True, exist_ok=True)
                    overlay.path.write_text(overlay.after_content, encoding="utf-8")
        except OSError as exc:
            for decision in plan.decisions:
                for overlay in decision.overlays.values():
                    project_root = overlay.path.parent.parent.parent
                    paths_to_restore: list[Path] = [overlay.path]
                    if overlay.rename_from is not None:
                        paths_to_restore.append(overlay.rename_from)
                    for path in paths_to_restore:
                        rel = path.relative_to(project_root)
                        existed = subprocess.run(
                            ["git", "-C", str(project_root), "cat-file", "-e", f"HEAD:{rel}"],
                            capture_output=True,
                        ).returncode == 0
                        if existed:
                            subprocess.run(
                                ["git", "-C", str(project_root), "checkout", "HEAD", "--", str(rel)],
                                check=False,
                            )
                        else:
                            path.unlink(missing_ok=True)
            raise PromoteWriteError(
                stage="rewrite_projects",
                detail=f"overlay write failed: {exc}",
                commons_commit=commons_commit,
                projects_touched=projects_touched,
            ) from exc

        # ---------- Step 7: write audit log (success path) ----------
        current_stage = "audit"
        finished_at = datetime.now(tz=timezone.utc)
        result = PromoteResult(
            op_id=op_id,
            started_at=started_at,
            finished_at=finished_at,
            commons_commit=commons_commit,
            tags_created=tags_created,
            decisions=plan.decisions,
            failed_candidates=plan.failed_candidates,
            audit_log_path=None,
            status="ok",
            failure_stage=None,
            failure_detail=None,
            projects_touched=projects_touched,
        )
        try:
            audit_path = _write_audit_log(result, commons_root, invocation=invocation)
            audit_rel = str(audit_path.relative_to(commons_root))
            _git(commons_root, "add", "--", audit_rel)
            _git(commons_root, "commit", "-m", f"audit: op {op_id}", "--", audit_rel)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise PromoteWriteError(
                stage="audit",
                detail=f"audit log write/commit failed: {exc}",
                commons_commit=commons_commit,
                projects_touched=projects_touched,
            ) from exc

        return PromoteResult(
            op_id=result.op_id,
            started_at=result.started_at,
            finished_at=result.finished_at,
            commons_commit=result.commons_commit,
            tags_created=result.tags_created,
            decisions=result.decisions,
            failed_candidates=result.failed_candidates,
            audit_log_path=audit_path,
            status="ok",
            failure_stage=None,
            failure_detail=None,
            projects_touched=result.projects_touched,
        )

    except (PromoteInputError, PromoteWriteError, PromoteCandidateError) as exc:
        stage = getattr(exc, "stage", None) or current_stage
        audit_path, audit_yaml = _write_failure_audit_log(
            op_id=op_id,
            started_at=started_at,
            commons_root=commons_root,
            commons_commit=commons_commit,
            tags_created=tags_created,
            plan=plan,
            projects_touched=projects_touched,
            failure_stage=stage,
            failure_detail=str(exc),
            invocation=invocation,
        )
        if audit_path is None:
            exc.failure_audit_yaml = audit_yaml  # type: ignore[attr-defined]
        raise


# --------------------------------------------------------------------------- #
# Private helpers                                                              #
# --------------------------------------------------------------------------- #

_BIBKEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,63}$")

# Sentinel keys for stashing raw frontmatter+body in PromoteCandidate.project_only_body
# during discovery, to be consumed by _classify_entity in plan_promote (Task 11).
# Defined as module-level constants so the coupling between discovery and
# classification is greppable rather than hidden in two string literals.
_RAW_FRONTMATTER_KEY = "__raw_frontmatter__"
_RAW_BODY_KEY = "__raw_body__"


def _normalize_bibkey_for_match(raw: str) -> str:
    """Strip `.md`, casefold for dedup grouping. Raises PromoteCandidateError on
    empty / whitespace / regex-failing inputs. Does NOT mutate canonical case."""
    if raw is None:
        raise PromoteCandidateError("bibkey is None")
    stripped = raw.strip()
    if not stripped:
        raise PromoteCandidateError("bibkey is empty / whitespace")
    if stripped.endswith(".md"):
        stripped = stripped[:-3]
    if not _BIBKEY_RE.match(stripped):
        raise PromoteCandidateError(
            f"bibkey {raw!r} does not match [A-Za-z][A-Za-z0-9-]{{1,63}}"
        )
    return stripped.casefold()


def _classify_paper_file_kind(
    frontmatter: dict,
) -> Literal["paper", "skip-other-kind", "skip-other-id"]:
    """Decide whether a file under `doc/papers/` is a paper candidate.

    Rule (design §6.3 step 2):
    1. Explicit `kind: paper` or `type: paper` → paper.
    2. Explicit `kind` / `type` with any other value → skip-other-kind.
    3. No `kind` / `type`, `id` present and NOT starting with `paper:` →
       skip-other-id (defense-in-depth; stronger declaration than directory
       inference, but weaker than an explicit kind/type).
    4. No `kind` / `type` and no contradictory `id` → infer from directory: paper.

    Rules are checked in order: explicit kind/type wins over the id-prefix
    check, so `{"id": "dataset:foo", "kind": "paper"}` returns "paper".
    """
    kind_val = frontmatter.get("kind") or frontmatter.get("type")
    if kind_val == "paper":
        return "paper"
    if kind_val is not None:
        return "skip-other-kind"
    id_val = frontmatter.get("id")
    if isinstance(id_val, str) and not id_val.startswith("paper:"):
        return "skip-other-id"
    return "paper"


logger = logging.getLogger(__name__)


def _parse_paper_file(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises PromoteCandidateError on
    parse failure, unreadable file, or missing frontmatter delimiters."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PromoteCandidateError(
            f"unreadable file: {exc}", path=path
        ) from exc
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != "---":
        raise PromoteCandidateError("no frontmatter (missing leading ---)", path=path)
    closing_idx: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_idx = idx
            break
    if closing_idx is None:
        raise PromoteCandidateError("no frontmatter (missing closing ---)", path=path)
    yaml_block = "\n".join(lines[1:closing_idx])
    try:
        fm = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        raise PromoteCandidateError(
            f"frontmatter parse error: {exc}", path=path
        ) from exc
    if not isinstance(fm, dict):
        raise PromoteCandidateError(
            "frontmatter is not a mapping", path=path
        )
    body = "\n".join(lines[closing_idx + 1 :])
    if text.endswith("\n") and not body.endswith("\n"):
        body += "\n"
    return fm, body


def _scan_project_papers(
    project_root: Path, project_slug: str
) -> tuple[list[PromoteCandidate], list[FailedCandidate]]:
    """Walk `<project_root>/doc/papers/*.md`, classify each file, return
    (candidates, failures). Skips already-promoted files and explicit non-paper
    kinds. Per-file failures become FailedCandidate records; the walk continues."""
    candidates: list[PromoteCandidate] = []
    failures: list[FailedCandidate] = []
    papers_dir = project_root / "doc" / "papers"
    if not papers_dir.is_dir():
        return candidates, failures

    for md_path in sorted(papers_dir.glob("*.md")):
        try:
            fm, body = _parse_paper_file(md_path)
        except PromoteCandidateError as exc:
            failures.append(
                FailedCandidate(
                    bibkey=md_path.stem,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=str(exc),
                )
            )
            continue

        if "overlay_of" in fm:
            continue  # already promoted; idempotent skip

        classification = _classify_paper_file_kind(fm)
        if classification == "skip-other-kind":
            logger.warning(
                "%s: kind/type is not 'paper'; skipping (explicit non-paper)",
                md_path,
            )
            continue
        if classification == "skip-other-id":
            logger.warning(
                "%s: id prefix is not 'paper:'; skipping (explicit non-paper id)",
                md_path,
            )
            continue

        # Commons / overlay adapters derive ids from filename stems case-
        # sensitively and require frontmatter id to match the stem exactly
        # (adapter.py:149, overlay.py:114). Promote inherits the same rule —
        # the source case is canonical (design §4.1.3). If the source carries
        # an explicit `id:` that disagrees with its filename stem, that's a
        # bug in the source file, not something promote should silently
        # rewrite: fail the candidate so the user can fix it.
        explicit_id = fm.get("id")
        if explicit_id is not None and explicit_id != f"paper:{md_path.stem}":
            failures.append(
                FailedCandidate(
                    bibkey=md_path.stem,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=(
                        f"frontmatter id {explicit_id!r} does not match filename "
                        f"stem {md_path.stem!r}; expected id 'paper:{md_path.stem}'"
                    ),
                )
            )
            continue

        bibkey_source = md_path.stem
        try:
            bibkey_normalized = _normalize_bibkey_for_match(bibkey_source)
        except PromoteCandidateError as exc:
            failures.append(
                FailedCandidate(
                    bibkey=bibkey_source,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=str(exc),
                )
            )
            continue

        # canonical_fields / project_only_fields / body splits are filled in
        # later by `_classify_entity` (Task 11). For now we stash raw frontmatter
        # + body so discovery is independent of merge-policy lookup.
        candidates.append(
            PromoteCandidate(
                bibkey=bibkey_source,
                bibkey_normalized=bibkey_normalized,
                project_slug=project_slug,
                project_root=project_root,
                overlay_source_path=md_path,
                canonical_fields={},
                project_only_fields={},
                canonical_body={},
                project_only_body={_RAW_FRONTMATTER_KEY: fm, _RAW_BODY_KEY: body},
            )
        )

    return candidates, failures


# --------------------------------------------------------------------------- #
# _classify_entity helpers (Task 11)                                          #
# --------------------------------------------------------------------------- #

# Overlay-only fields that MUST never leak onto the canonical or project-only
# field dicts (the overlay-rewrite step writes these directly).
_OVERLAY_ONLY_KEYS: frozenset[str] = frozenset({"overlay_of", "pin_version", "pin_effective_version"})

# Base-required fields that the promote tool generates on the canonical side
# and that MUST NOT be copied from source. `created` / `updated` are NOT here:
# they have `science:merge: project_only` in the paper schema, so the policy
# lookup routes them correctly to the project_only bucket. The canonical
# writer fills its own `created` / `updated` from the apply timestamp.
_GENERATED_BY_PROMOTE_KEYS: frozenset[str] = frozenset(
    {"schema_profile", "version"}
)

# Identity fields promote re-derives from the PromoteDecision after the
# canonical bibkey case is picked. They are stripped from the canonical merge
# bucket so case-divergent overlays don't surface a bogus `id` conflict
# (design §4.1.3).
_PROMOTE_DERIVED_IDENTITY_KEYS: frozenset[str] = frozenset({"id", "type", "bibkey"})


def _split_body_by_headings(body: str) -> dict[str, str]:
    """Parse a markdown body into `{heading: content_after_heading}`.

    Only `## ` (level-2) headings are tracked. Content before the first `## ` is
    keyed as `""` (the empty string). Sub-headings (`###` etc.) stay inside
    whichever level-2 section contains them.
    """
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return {heading: "\n".join(lines) for heading, lines in sections.items() if lines or heading}


def _classify_entity(
    frontmatter: dict,
    body: str,
    merge_policy: dict[str, MergePolicy],
    canonical_body_sections: list[str],
) -> tuple[dict, dict, dict[str, str], dict[str, str]]:
    """Split (frontmatter, body) into (canonical_fields, project_only_fields,
    canonical_body, project_only_body).

    - Promote-generated fields (schema_profile, version) are NOT copied from
      source; the canonical writer fills them. `created` / `updated` are
      schema-tagged `project_only` and route to the overlay via the policy
      lookup — the canonical writer fills its own from the apply timestamp.
    - Overlay-management fields (overlay_of, pin_version) NEVER appear on either
      side (they're written by the overlay renderer alone).
    - Promote-derived identity fields (id, type, bibkey) NEVER appear on either
      side either — the canonical writer re-emits them from the PromoteDecision
      (after `_pick_canonical_bibkey_case` chooses the canonical-case bibkey).
      Letting them flow through the canonical bucket would surface a bogus
      `id` conflict any time two case-divergent overlays merge (design §4.1.3).
    - For every remaining source field, the merge policy decides:
        REPLACE / APPEND / FORBIDDEN → canonical bucket
        PROJECT_ONLY                  → project-only bucket
        no policy entry               → conservative default: project-only
    - `authors` is coerced to list[str] if it arrives as a string.
    - `journal` is renamed to `venue` (one-time coercion).
    """
    canonical: dict = {}
    project_only: dict = {}
    for key, value in frontmatter.items():
        if key in _OVERLAY_ONLY_KEYS:
            continue
        if key in _PROMOTE_DERIVED_IDENTITY_KEYS:
            continue
        if key in _GENERATED_BY_PROMOTE_KEYS:
            continue
        if key == "journal":
            canonical["venue"] = value
            continue
        if key == "authors" and not isinstance(value, list):
            canonical["authors"] = [str(value)]
            continue
        # `tags` uses APPEND policy in the schema but promote always writes
        # canonical `tags: []` (design §4.1.2) so the source's tags stay
        # project-only during classification; the renderer zeros out canonical tags.
        if key == "tags":
            project_only[key] = value
            continue
        policy = merge_policy.get(key, MergePolicy.PROJECT_ONLY)
        if policy == MergePolicy.PROJECT_ONLY:
            project_only[key] = value
        else:
            canonical[key] = value

    raw_body_sections = _split_body_by_headings(body)
    canonical_set = {s.casefold() for s in canonical_body_sections}
    canonical_body: dict[str, str] = {}
    project_only_body: dict[str, str] = {}
    for heading, content in raw_body_sections.items():
        if heading == "":
            project_only_body[""] = content
            continue
        if heading.casefold() in canonical_set:
            canonical_body[heading] = content
        else:
            project_only_body[heading] = content

    return canonical, project_only, canonical_body, project_only_body


# --------------------------------------------------------------------------- #
# Multi-instance merge helpers (Task 12)                                       #
# --------------------------------------------------------------------------- #


def _merge_canonical_fields(
    candidates: list[PromoteCandidate],
    merge_policy: dict[str, MergePolicy],
) -> tuple[dict, list[FieldConflict]]:
    """Merge canonical_fields across N candidates of the same bibkey.

    Rule per field (driven by merge_policy lookup):
    - APPEND: union of all candidates' lists, sorted + deduped.
    - Anything else (REPLACE / FORBIDDEN / no entry):
      - if no candidate has the field → omitted.
      - if all candidates agree (equal values) → that value.
      - if candidates disagree → field omitted from `merged`; a FieldConflict
        with `{slug: value}` for every candidate that has the field is appended.
    """
    all_keys = {key for c in candidates for key in c.canonical_fields}
    merged: dict = {}
    conflicts: list[FieldConflict] = []

    for key in sorted(all_keys):
        present = [c for c in candidates if key in c.canonical_fields]
        policy = merge_policy.get(key, MergePolicy.REPLACE)
        if policy == MergePolicy.APPEND:
            union: set = set()
            for c in present:
                v = c.canonical_fields[key]
                if isinstance(v, list):
                    union.update(v)
                else:
                    union.add(v)
            merged[key] = sorted(union)
            continue

        values = [c.canonical_fields[key] for c in present]
        if all(v == values[0] for v in values):
            merged[key] = values[0]
        else:
            conflicts.append(
                FieldConflict(
                    bibkey=present[0].bibkey,
                    field=key,
                    candidates={c.project_slug: c.canonical_fields[key] for c in present},
                )
            )

    return merged, conflicts


def _pick_canonical_bibkey_case(
    candidates: list[PromoteCandidate],
    from_order: list[str],
) -> str:
    """Pick the canonical bibkey case from a multi-instance group.

    Rule (design §4.1.3):
    1. Walk from_order; the first project_slug with a matching candidate wins.
    2. If two candidates share the earliest slug (impossible in practice but
       defensive) or from_order is empty, tie-break by lexical project_slug.
    """
    order = {slug: idx for idx, slug in enumerate(from_order)}
    sorted_by_order = sorted(
        candidates,
        key=lambda c: (order.get(c.project_slug, len(order)), c.project_slug),
    )
    return sorted_by_order[0].bibkey


# --------------------------------------------------------------------------- #
# Renderer helpers (Task 13)                                                   #
# --------------------------------------------------------------------------- #

_DATE_KEYS: frozenset[str] = frozenset({"created", "updated"})
# Scalar keys whose values must be emitted as double-quoted strings regardless
# of how pyyaml chooses to serialise them (version strings look numeric to YAML).
_FORCE_QUOTED_KEYS: frozenset[str] = _DATE_KEYS | frozenset({"version", "pin_version"})


def _coerce_date_for_yaml(value: Any) -> str:
    """`datetime.date` / `datetime.datetime` / `str` → ISO-8601 string. Other
    types are returned as-is via `str(value)`."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _render_frontmatter(fields: dict) -> str:
    """Render an ordered, deterministic YAML frontmatter block.

    Date fields go through `_coerce_date_for_yaml` and are quoted; version /
    pin_version scalars are also force-quoted (pyyaml treats "1.0.0" as a
    plain float-like scalar).  Lists are block style.
    """
    out: dict = {}
    for key, value in fields.items():
        if key in _DATE_KEYS:
            out[key] = _coerce_date_for_yaml(value)
        else:
            out[key] = value
    dumped = yaml.safe_dump(
        out,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )
    # Force double-quoting of scalars in _FORCE_QUOTED_KEYS — pyyaml may emit
    # unquoted or single-quoted forms that would round-trip incorrectly.
    lines = []
    for line in dumped.splitlines():
        for k in _FORCE_QUOTED_KEYS:
            prefix = f"{k}:"
            if line.startswith(prefix):
                raw = line[len(prefix):].strip()
                # Strip surrounding single- or double-quotes pyyaml may add
                if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
                    raw = raw[1:-1]
                if raw and raw != "null":
                    line = f'{k}: "{raw}"'
        lines.append(line)
    return "\n".join(lines) + "\n"


def _render_body(sections: dict[str, str]) -> str:
    """Render `{heading: content}` back to markdown. Empty heading "" goes first
    (intro prose); the rest are emitted in insertion order with `## ` prefix."""
    parts: list[str] = []
    if "" in sections:
        intro = sections[""].strip("\n")
        if intro:
            parts.append(intro + "\n")
    for heading, content in sections.items():
        if heading == "":
            continue
        parts.append(f"## {heading}\n{content.rstrip()}\n")
    return "\n".join(parts)


def _render_canonical(
    decision: PromoteDecision,
    *,
    canonical_fields: dict,
    canonical_body: dict[str, str],
    created: date,
    updated: date,
) -> str:
    """Render the commons-side papers/<bibkey>.md content.

    Fills base-required fields (schema_profile, version, created, updated) and
    always emits `tags: []` so the per-project overlay-merge produces only the
    project's overlay tags (design §4.1.2).
    """
    profile_str = default_profile_for_kind("paper").render()
    head: dict = {
        "schema_profile": profile_str,
        "id": f"paper:{decision.bibkey}",
        "type": "paper",
        "title": canonical_fields.get("title", ""),
        "version": decision.canonical_version,
        "created": _coerce_date_for_yaml(created),
        "updated": _coerce_date_for_yaml(updated),
        "bibkey": decision.bibkey,
        "tags": [],
    }
    for k, v in canonical_fields.items():
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(canonical_body)
    return f"---\n{fm}---\n{body}"


def _render_overlay(
    decision: PromoteDecision,
    *,
    project_slug: str,  # noqa: ARG001 — retained for Task 15 audit-log call-site symmetry
    project_only_fields: dict,
    project_only_body: dict[str, str],
) -> str:
    """Render a project-side overlay file. NEVER emits schema_profile; the
    overlay validator is hardcoded to overlay/1.1 (design §4.4)."""
    head: dict = {
        "id": f"paper:{decision.bibkey}",
        "overlay_of": f"paper:{decision.bibkey}",
        "pin_version": decision.canonical_version,
    }
    # Skip overlay-only-management keys (overlay_of/pin_version/pin_effective_version)
    # AND any head-priority key, so project_only_fields can't accidentally
    # overwrite the promote-derived id/overlay_of/pin_version (mirrors
    # _render_canonical's guard pattern).
    for k, v in project_only_fields.items():
        if k in _OVERLAY_ONLY_KEYS:
            continue
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(project_only_body)
    return f"---\n{fm}---\n{body}"


# --------------------------------------------------------------------------- #
# Apply-phase helpers (Task 15)                                                #
# --------------------------------------------------------------------------- #


def _git(commons_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run `git -C <commons_root> <args>` and return the CompletedProcess.

    Wrapping makes path-limited call sites readable and centralizes the cwd
    plumbing so individual helpers don't repeat `["git", "-C", str(root), ...]`.
    """
    return subprocess.run(
        ["git", "-C", str(commons_root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _build_project_rollback_command(overlay_rewrites: list[dict]) -> str:
    """Build a concrete `git checkout HEAD -- <paths>` command for one project,
    given its overlay_rewrites entries from the audit log. Each entry's `path`
    is an absolute `<project_root>/doc/papers/<file>.md`; we strip the trailing
    `doc/papers/<file>.md` to recover the project_root."""
    if not overlay_rewrites:
        return ""
    first_path = Path(overlay_rewrites[0]["path"])
    project_root = first_path.parents[2]
    rels = sorted(
        str(Path(entry["path"]).relative_to(project_root))
        for entry in overlay_rewrites
    )
    return f"git -C {project_root} checkout HEAD -- {' '.join(rels)}"


def _render_audit_log_yaml(
    result: PromoteResult,
    commons_root: Path,
    *,
    invocation: str,
) -> str:
    """Serialize the audit log dict to YAML. Pure function — no disk I/O.
    Used by both the success path (which then writes + commits) and the
    failure path (which writes uncommitted, or falls back to stderr if the
    write itself fails)."""
    touched_set = set(result.projects_touched)
    projects_touched: dict = {}
    for decision in result.decisions:
        for slug, overlay in decision.overlays.items():
            if slug not in touched_set:
                continue
            projects_touched.setdefault(slug, {"overlay_rewrites": []})
            entry: dict = {
                "bibkey": decision.bibkey,
                "path": str(overlay.path),
                "pin_version": overlay.pin_version,
            }
            if overlay.rename_from is not None:
                entry["rename"] = {
                    "from": overlay.rename_from.name,
                    "to": overlay.path.name,
                }
            projects_touched[slug]["overlay_rewrites"].append(entry)

    log: dict = {
        "op_id": result.op_id,
        "type": "paper",
        "invocation": invocation,
        "status": result.status,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "commons_commit": result.commons_commit,
        "commons_tags": result.tags_created,
        "projects_touched": projects_touched,
        "conflict_resolutions": [
            {
                "bibkey": cr.bibkey,
                "field": cr.field,
                "candidates": cr.candidates,
                "resolved_to": cr.resolved_to,
                "source_project": cr.source_project,
            }
            for d in result.decisions
            for cr in d.resolved_conflicts
        ],
        "failed_candidates": [
            {
                "bibkey": f.bibkey,
                "project_slug": f.project_slug,
                "source_path": str(f.source_path),
                "error_class": f.error_class,
                "error_message": f.error_message,
            }
            for f in result.failed_candidates
        ],
        "rollback": {
            "commons": (
                f"git -C {commons_root} revert {result.commons_commit}"
                if result.commons_commit else None
            ),
            # Per design §6.5: each entry is a copy-pasteable git command,
            # not a placeholder. Derive project_root by walking up from each
            # overlay path (`<root>/doc/papers/<file>`) and list every rewritten
            # path so the operator can restore exactly the touched files.
            "projects": {
                slug: _build_project_rollback_command(rewrites["overlay_rewrites"])
                for slug, rewrites in projects_touched.items()
            },
        },
    }
    if result.failure_stage:
        log["failure_stage"] = result.failure_stage
        log["failure_detail"] = result.failure_detail

    return yaml.safe_dump(log, sort_keys=False, allow_unicode=True)


def _write_audit_log(
    result: PromoteResult,
    commons_root: Path,
    *,
    invocation: str,
) -> Path:
    """Write the per-op YAML audit log under `<commons_root>/.migrations/`.

    Filename: `<UTC-YYYYMMDDTHHMMSSZ>-<op_id>.yaml`. The log is NOT committed
    here — `apply_promote` commits it path-limited on the success path; failure
    paths use `_write_failure_audit_log` (which calls the same renderer but
    tolerates write failure).
    """
    migrations = commons_root / ".migrations"
    migrations.mkdir(exist_ok=True)
    stamp = result.started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = migrations / f"{stamp}-{result.op_id}.yaml"
    path.write_text(
        _render_audit_log_yaml(result, commons_root, invocation=invocation),
        encoding="utf-8",
    )
    return path


def _rollback_step5(
    commons_root: Path,
    tags_attempted: list[str],
    canonical_paths: list[Path],
) -> None:
    """Non-destructive path-limited rollback for a step-5 mid-failure.

    1. Delete every tag in `tags_attempted` (idempotent — tags that never
       existed silently no-op).
    2. `git reset --soft HEAD~1` — moves HEAD back without disturbing index/wt.
    3. For each canonical_path: if it exists at the new HEAD, `git checkout
       HEAD -- <path>`. If it does NOT exist at HEAD (first-promote), unlink
       the working-tree file.

    Caller must have verified that HEAD~1 is the pre-step-4 state (the immediate
    parent of the just-undone promote commit). NEVER calls `reset --hard`.
    """
    for tag in tags_attempted:
        _git(commons_root, "tag", "-d", tag, check=False)

    _git(commons_root, "reset", "--soft", "HEAD~1")

    for canonical_path in canonical_paths:
        rel = canonical_path.relative_to(commons_root)
        exists_at_head = (
            _git(commons_root, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0
        )
        if exists_at_head:
            _git(commons_root, "checkout", "HEAD", "--", str(rel))
        else:
            canonical_path.unlink(missing_ok=True)

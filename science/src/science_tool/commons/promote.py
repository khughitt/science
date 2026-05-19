"""Promote paper entities from per-project files into the commons store.

Pipeline: discover → plan → apply. Atomic-batch transaction semantics
per docs/plans/2026-05-15-commons-promote-papers-design.md §6.3.

This module owns:
- Dataclasses for the public surface (PromoteCandidate, PromotePlan, …).
- `discover_candidates(project_slugs, kind) -> DiscoveryResult`.
- `plan_promote(discovery, *, commons_root, kind, from_order, resolve_conflict) -> PromotePlan` (Task 14).
- `apply_promote(plan, commons_root, *, invocation) -> PromoteResult` (Tasks 16–17).
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from importlib import import_module
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
    read_overlay_merge_policy,
)
from science_model.entity_schema.profile import ProfileComponent
from science_tool.commons.datapackage import (
    render_canonical_datapackage_yaml,
    stream_sha256_and_bytes,
)
from science_tool.commons.config import check_override_conflict, resolve_project_by_id
from science_tool.commons.errors import (
    CommonsError,
    PromoteCandidateError,
    PromoteConflictAbort,
    PromoteInputError,
    PromoteResourceMissingError,
    PromoteValidationError,
    PromoteWriteError,
)


class EligibilityVerdict(Enum):
    ELIGIBLE = "eligible"
    SKIP_SILENT = "skip_silent"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class SideChannelContext:
    decision: PromoteDecision
    plan: PromotePlan
    commons_root: Path
    op_id: str


@dataclass(frozen=True, slots=True)
class SideChannelResult:
    artifact_paths: list[Path]
    backup_paths: list[Path]


def _dataset_side_channel_apply(ctx: SideChannelContext) -> SideChannelResult:
    from science_tool.commons.config import (
        _data_yaml_path,
        _upsert_data_override,
        check_override_conflict,
    )

    extras = ctx.plan.dataset_audit_extras.get(ctx.decision.slug)
    if extras is None or "override_path" not in extras:
        raise PromoteCandidateError(
            "dataset side-channel apply requires override_path audit extra",
            slug=ctx.decision.slug,
        )
    override_path = extras["override_path"]
    if not isinstance(override_path, str | os.PathLike):
        raise PromoteCandidateError(
            "dataset side-channel apply requires string override_path audit extra",
            slug=ctx.decision.slug,
        )
    override_path = Path(override_path)
    check_override_conflict(slug=ctx.decision.slug, planned_path=override_path)
    _upsert_data_override(
        slug=ctx.decision.slug,
        absolute_path=override_path,
        op_id=ctx.op_id,
        allow_existing_backup=True,
    )
    yaml_path = _data_yaml_path()
    backup_path = yaml_path.parent / f"data.yaml.bak.{ctx.op_id}"
    absent_sentinel_path = yaml_path.parent / f"data.yaml.bak.{ctx.op_id}.absent"
    actual_backup = backup_path if backup_path.exists() else absent_sentinel_path
    return SideChannelResult(
        artifact_paths=[yaml_path],
        backup_paths=[actual_backup],
    )


@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    """Per-kind configuration for the promote pipeline.

    One instance per kind ("paper", "topic", "theme", "dataset"). Pure data plus an
    optional eligibility-filter callable; threaded through discovery /
    plan / apply via the `kind` parameter or `PromotePlan.kind`.
    """

    kind: Literal["paper", "topic", "theme", "dataset"]
    source_subdirs: tuple[str, ...]
    overlay_dest_subdir: str
    commons_subdir: str
    id_prefix: str
    slug_regex: re.Pattern[str]
    slug_match: Literal["casefold", "exact"]
    mixin_schema_id: str
    default_profile: "ProfileString"
    eligibility_filter: Callable[[Mapping[str, Any]], "EligibilityVerdict"] | None
    filename_prefix: str = ""
    slug_from_id: bool = False
    side_channel_apply: Callable[[SideChannelContext], SideChannelResult] | None = None


PROMOTE_KIND_PAPER = PromoteKindConfig(
    kind="paper",
    source_subdirs=("doc/papers",),
    overlay_dest_subdir="doc/papers",
    commons_subdir="papers",
    id_prefix="paper:",
    slug_regex=re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,63}$"),
    slug_match="casefold",
    mixin_schema_id="https://schemas.science/mixin-paper-2.0.json",
    default_profile=default_profile_for_kind("paper"),
    eligibility_filter=None,
)

PROMOTE_KIND_TOPIC = PromoteKindConfig(
    kind="topic",
    source_subdirs=("doc/topics", "doc/background/topics"),
    overlay_dest_subdir="doc/topics",
    commons_subdir="topics",
    id_prefix="topic:",
    slug_regex=re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$"),
    slug_match="exact",
    mixin_schema_id="https://schemas.science/mixin-topic-2.0.json",
    default_profile=default_profile_for_kind("topic"),
    eligibility_filter=None,
)


def _theme_eligibility(fm: Mapping[str, Any]) -> EligibilityVerdict:
    """Theme eligibility filter (design §3.1).

    Only `theme_scope: cross-project` is eligible. `theme_scope: project` is
    skipped silently (debug-log + drop). Missing/malformed scope is a hard
    fail recorded as a `FailedCandidate`.
    """
    scope = fm.get("theme_scope")
    if scope == "cross-project":
        return EligibilityVerdict.ELIGIBLE
    if scope == "project":
        return EligibilityVerdict.SKIP_SILENT
    return EligibilityVerdict.FAIL


PROMOTE_KIND_THEME = PromoteKindConfig(
    kind="theme",
    source_subdirs=("doc/themes",),
    overlay_dest_subdir="doc/themes",
    commons_subdir="themes",
    id_prefix="theme:",
    slug_regex=re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$"),
    slug_match="exact",
    mixin_schema_id="https://schemas.science/mixin-theme-2.0.json",
    default_profile=default_profile_for_kind("theme"),
    eligibility_filter=_theme_eligibility,
)


PROMOTE_KIND_DATASET = PromoteKindConfig(
    kind="dataset",
    source_subdirs=("doc/datasets",),
    overlay_dest_subdir="doc/datasets",
    commons_subdir="datasets",
    id_prefix="dataset:",
    slug_regex=re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$"),
    slug_match="exact",
    mixin_schema_id="https://schemas.science/mixin-dataset-1.0.json",
    default_profile=default_profile_for_kind("dataset"),
    eligibility_filter=None,
    side_channel_apply=_dataset_side_channel_apply,
    filename_prefix="data-",
    slug_from_id=True,
)


# Bio extension classification used by `_validate_mixin_stacking`.
_STRUCTURAL_BIO_EXTENSIONS = frozenset({"bio.matrix", "bio.table"})
_DOMAIN_BIO_EXTENSIONS = frozenset({"bio.rnaseq", "bio.scrna", "bio.cna"})


def _validate_mixin_stacking(
    extensions: tuple["ProfileComponent", ...],
) -> None:
    """Enforce Phase H stacking rules on a resolved `--mixin` tuple.

    Rules:
      - At most one structural mixin (bio.matrix xor bio.table).
      - At most one domain mixin (bio.rnaseq xor bio.scrna xor bio.cna).

    Unknown bio.* names (e.g. `--mixin bio.bogus/1.0` in explicit form)
    are NOT rejected here. They sail through to `plan_promote`'s
    `read_merge_policy(active_profile)` call, where the loader raises
    `SchemaNotFoundError`; the plan_promote-side try/except (Task 12)
    catches that and rewraps as `PromoteMixinResolutionError`.
    `_validate_artifact` (Task 13) also catches the same exception as
    belt-and-suspenders for the rare case where canonical content
    already cites a missing extension. Sugar form (`--mixin
    bio.bogus`) is caught earlier still -- by `_resolve_mixin_arg` in
    cli.py before plan_promote runs.
    """
    from science_tool.commons.errors import PromoteMixinStackingError

    structural: list[str] = []
    domain: list[str] = []
    for ext in extensions:
        if ext.name in _STRUCTURAL_BIO_EXTENSIONS:
            structural.append(ext.name)
        elif ext.name in _DOMAIN_BIO_EXTENSIONS:
            domain.append(ext.name)
        # else: unknown bio.* extension -- pass through; plan_promote's
        # active-profile setup will fail loud via SchemaNotFoundError.
    if len(structural) > 1:
        raise PromoteMixinStackingError(
            f"--mixin: at most one structural bio extension allowed "
            f"(got {', '.join(structural)})."
        )
    if len(domain) > 1:
        raise PromoteMixinStackingError(
            f"--mixin: at most one domain bio extension allowed "
            f"(got {', '.join(domain)})."
        )


def _active_profile(
    kind: PromoteKindConfig,
    extensions: tuple["ProfileComponent", ...],
) -> "ProfileString":
    """Build the per-call ProfileString from a kind's default plus extensions.

    Introduced for the Phase H plan_promote path to drive merge policy,
    body sections, and canonical rendering through
    `read_merge_policy(active_profile)` etc., instead of
    `kind.default_profile` which omits the Phase H extensions.
    """
    return ProfileString(
        base=kind.default_profile.base,
        mixin=kind.default_profile.mixin,
        extensions=tuple(extensions),
    )


# --------------------------------------------------------------------------- #
# Public dataclasses                                                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PromoteCandidate:
    """One paper file found during discovery.

    `slug` is the source's case (filename stem). `slug_normalized` is
    casefold() used only for dedup grouping. See design §4.1.3.
    """

    slug: str
    slug_normalized: str
    project_slug: str
    project_root: Path
    overlay_source_path: Path
    canonical_fields: dict[str, Any]
    project_only_fields: dict[str, Any]
    canonical_body: dict[str, str]
    project_only_body: dict[str, Any]
    datapackage_source_path: Path | None = None
    datapackage_doc: dict[str, Any] | None = None
    # `project_only_body` is `dict[str, Any]` (not `[str, str]`) so the
    # discovery phase can stash the raw `(frontmatter, body)` pair under
    # sentinel keys `__raw_frontmatter__` / `__raw_body__` for `plan_promote`
    # to consume during classification. After `_classify_entity` runs in
    # `plan_promote`, the dict's values are pure `str` again.


@dataclass(frozen=True, slots=True)
class FieldConflict:
    slug: str
    kind: Literal["paper", "topic", "theme", "dataset"]
    field: str
    candidates: dict[str, Any]  # project_slug → value


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    slug: str
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
    unlinked_source: Path | None = None  # set when the original source path is replaced


@dataclass(frozen=True, slots=True)
class CanonicalArtifact:
    """One file under <commons_root>/<commons_subdir>/<slug>/.

    `path` is stored relative to the commons root (e.g.
    `datasets/foo/entity.md`). Apply resolves it against `commons_root` once
    at write time and records the absolute resolved path in the per-op
    rollback context so existing helpers (`_restore_paths_to_head`,
    `_rollback_step5`) keep their absolute-path signatures.
    """

    path: Path
    content: str
    validator: Literal["entity-mixin", "frictionless-datapackage", "plain"]


@dataclass(frozen=True, slots=True)
class PromoteDecision:
    slug: str
    canonical_artifacts: list[CanonicalArtifact]  # one or more commons-relative files
    canonical_version: str  # "1.0.0" etc.
    overlays: dict[str, OverlayRewrite]  # project_slug → rewrite plan
    resolved_conflicts: tuple[ConflictResolution, ...]


@dataclass(frozen=True, slots=True)
class FailedCandidate:
    slug: str | None
    project_slug: str
    source_path: Path
    error_class: str
    error_message: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates_by_slug: dict[str, list[PromoteCandidate]]
    failed_candidates: list[FailedCandidate]


@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    kind: PromoteKindConfig
    dataset_audit_extras: dict[str, dict[str, Any]] = field(default_factory=dict)


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
    failure_stage: (
        Literal[
            "preflight",
            "validate",
            "discover",
            "plan",
            "write_commons",
            "side_channel",
            "rewrite_projects",
            "audit",
        ]
        | None
    )
    failure_detail: str | None
    # Project slugs whose `doc/papers/<file>.md` were actually modified by this
    # operation. On the success path, every overlay slug; on a partial step-6
    # failure, just the slugs reached before the failure; on
    # preflight/tag/commit failures (no project file touched), the empty list.
    # The audit log filters `projects_touched` (overlay_rewrites + rollback
    # hints) by this list so failure logs don't suggest rollbacks for projects
    # that were never modified (design §6.3 step 7 failure variant).
    projects_touched: list[str]
    kind: PromoteKindConfig
    side_channel_results: dict[str, SideChannelResult] = field(default_factory=dict)
    plan_audit_extras: dict[str, dict[str, Any]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Public entry points (stubs — implemented in Tasks 10, 14, 16, 17)           #
# --------------------------------------------------------------------------- #


def discover_candidates(
    project_slugs: list[str],
    kind: PromoteKindConfig,
) -> DiscoveryResult:
    """Scan each project's `kind.source_subdirs` for promotion candidates.
    Group by `_normalize_slug_for_match(stem, kind)`. Returns successful
    candidates + failure records (no exception path for per-file failures).
    """
    grouped: dict[str, list[PromoteCandidate]] = {}
    failures: list[FailedCandidate] = []

    for slug in project_slugs:
        project_root = resolve_project_by_id(slug)  # raises CommonsError on bad slug
        candidates, project_failures = _scan_project(project_root, slug, kind)
        failures.extend(project_failures)
        for cand in candidates:
            grouped.setdefault(cand.slug_normalized, []).append(cand)

    return DiscoveryResult(candidates_by_slug=grouped, failed_candidates=failures)


def prompt_resolve(conflict: FieldConflict) -> Any:
    """Interactive terminal prompt — the default `resolve_conflict` callback.

    UI mirrors design §7.1. Returns the resolved value (a candidate value, a
    user-entered manual value, or raises `PromoteConflictAbort` on 'a' / Ctrl-C).
    """
    click.echo(f'\nConflict for {conflict.kind}:{conflict.slug}, field "{conflict.field}":')
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
    *,
    commons_root: Path,
    kind: PromoteKindConfig,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
    from_order: list[str] | None = None,
) -> PromotePlan:
    """Build a PromotePlan from a DiscoveryResult.

    For each slug group:
      1. Run `_classify_entity` per candidate (consumes the raw frontmatter/body
         stashed by discovery in `project_only_body.__raw_*__`).
      2. Pick canonical slug case via `_pick_canonical_bibkey_case`.
      3. Merge canonical fields → `(merged_fields, conflicts)`.
      4. Resolve each conflict via `resolve_conflict`.
      5. Build PromoteDecision (canonical artifacts rendered, overlays planned).

    `from_order` defaults to the discovery's project_slug encounter order.
    `resolve_conflict` defaults to `prompt_resolve`.
    """
    if resolve_conflict is None:
        resolve_conflict = prompt_resolve

    merge_policy = read_merge_policy(kind.default_profile)
    body_sections = read_canonical_body_sections(kind.default_profile)
    overlay_field_keys = set(read_overlay_merge_policy())

    if from_order is None:
        from_order = []
        seen_slugs: set[str] = set()
        for cands in discovery.candidates_by_slug.values():
            for c in cands:
                if c.project_slug not in seen_slugs:
                    from_order.append(c.project_slug)
                    seen_slugs.add(c.project_slug)

    decisions: list[PromoteDecision] = []
    soft_failures: list[FailedCandidate] = list(discovery.failed_candidates)
    dataset_audit_extras: dict[str, dict[str, Any]] = {}

    for slug_norm in sorted(discovery.candidates_by_slug):
        raw_group = discovery.candidates_by_slug[slug_norm]

        classified: list[PromoteCandidate] = []
        dataset_dropped_by_project: dict[str, list[str]] = {}
        for c in raw_group:
            raw_fm = c.project_only_body.get(_RAW_FRONTMATTER_KEY)
            raw_body = c.project_only_body.get(_RAW_BODY_KEY, "")
            if not isinstance(raw_fm, dict):
                soft_failures.append(
                    FailedCandidate(
                        slug=c.slug,
                        project_slug=c.project_slug,
                        source_path=c.overlay_source_path,
                        error_class="PromoteCandidateError",
                        error_message="discovery payload missing raw frontmatter",
                    )
                )
                continue
            can_f, proj_f, can_b, proj_b = _classify_entity(
                raw_fm,
                raw_body,
                merge_policy,
                body_sections,
            )
            if kind.kind == "dataset":
                proj_f = {k: v for k, v in proj_f.items() if k in overlay_field_keys}
                dataset_dropped_by_project[c.project_slug] = _dataset_dropped_fields(
                    raw_fm,
                    canonical_fields=can_f,
                    project_only_fields=proj_f,
                )
            classified.append(
                PromoteCandidate(
                    slug=c.slug,
                    slug_normalized=c.slug_normalized,
                    project_slug=c.project_slug,
                    project_root=c.project_root,
                    overlay_source_path=c.overlay_source_path,
                    canonical_fields=can_f,
                    project_only_fields=proj_f,
                    canonical_body=can_b,
                    project_only_body=proj_b,
                    datapackage_source_path=c.datapackage_source_path,
                    datapackage_doc=c.datapackage_doc,
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
            target_path = _overlay_target_path(c, kind=kind, canonical_case=canonical_case)
            if source_path.name != target_path.name and target_path.exists():
                raise PromoteInputError(
                    f"case-rename collision in {c.project_slug}: cannot rename "
                    f"{source_path} → {target_path}; target already exists"
                )
            if source_path.parent != target_path.parent and target_path.exists():
                raise PromoteInputError(
                    f"overlay target collision in {c.project_slug}: cannot flatten "
                    f"{source_path} → {target_path}; target already exists"
                )

        dataset_primary: PromoteCandidate | None = None
        dataset_primary_per_resource: dict[str, tuple[str, int]] | None = None
        if kind.kind == "dataset":
            dataset_primary = _primary_candidate_for_plan(classified, from_order)
            dataset_primary_per_resource = _dataset_per_resource(dataset_primary)
            if (
                dataset_primary.datapackage_doc is None
                or dataset_primary.datapackage_source_path is None
            ):
                raise PromoteCandidateError(
                    "dataset planning requires discovery datapackage metadata",
                    slug=canonical_case,
                )
            _validate_dataset_group_datapackages(
                canonical_slug=canonical_case,
                primary=dataset_primary,
                candidates=classified,
                primary_per_resource=dataset_primary_per_resource,
            )
            check_override_conflict(
                slug=canonical_case,
                planned_path=dataset_primary.datapackage_source_path.parent,
            )

        merged, conflicts = _merge_canonical_fields(classified, merge_policy, kind=kind.kind)

        resolved_conflicts: list[ConflictResolution] = []
        for conflict in conflicts:
            resolved_value = resolve_conflict(conflict)
            source_project = next(
                (slug for slug, v in conflict.candidates.items() if v == resolved_value),
                None,
            )
            resolved_conflicts.append(
                ConflictResolution(
                    slug=canonical_case,
                    field=conflict.field,
                    candidates=conflict.candidates,
                    resolved_to=resolved_value,
                    source_project=source_project,
                )
            )
            merged[conflict.field] = resolved_value

        if kind.kind == "dataset":
            canonical_artifact_path = Path(kind.commons_subdir) / canonical_case / "entity.md"
        else:
            canonical_artifact_path = Path(kind.commons_subdir) / f"{canonical_case}.md"
        overlays: dict[str, OverlayRewrite] = {}
        for c in classified:
            source_path = c.overlay_source_path
            target_path = _overlay_target_path(c, kind=kind, canonical_case=canonical_case)
            rename_from = source_path if source_path.name != target_path.name else None
            unlinked_source = source_path if source_path.parent != target_path.parent else None
            if rename_from is not None and target_path.exists():
                raise PromoteInputError(
                    f"case-rename collision in {c.project_slug}: cannot rename "
                    f"{rename_from} → {target_path}; target already exists"
                )
            if source_path.parent != target_path.parent and target_path.exists():
                raise PromoteInputError(
                    f"overlay target collision in {c.project_slug}: cannot flatten "
                    f"{source_path} → {target_path}; target already exists"
                )
            project_only_fields = c.project_only_fields
            if kind.kind == "dataset":
                project_only_fields = dict(c.project_only_fields)
                if c.datapackage_source_path is not None:
                    project_only_fields["source"] = _project_relative_posix(
                        c.project_root,
                        c.datapackage_source_path,
                    )
            rendered_overlay = _render_overlay(
                PromoteDecision(
                    slug=canonical_case,
                    canonical_artifacts=[
                        CanonicalArtifact(
                            path=canonical_artifact_path,
                            content="",
                            validator="entity-mixin",
                        )
                    ],
                    canonical_version="1.0.0",
                    overlays={},
                    resolved_conflicts=(),
                ),
                project_only_fields=project_only_fields,
                project_only_body=c.project_only_body,
                kind=kind,
            )
            overlays[c.project_slug] = OverlayRewrite(
                project_slug=c.project_slug,
                path=target_path,
                before_sha="",
                after_content=rendered_overlay,
                pin_version="1.0.0",
                rename_from=rename_from,
                unlinked_source=unlinked_source,
            )

        canonical_decision = PromoteDecision(
            slug=canonical_case,
            canonical_artifacts=[
                CanonicalArtifact(
                    path=canonical_artifact_path,
                    content="",
                    validator="entity-mixin",
                )
            ],
            canonical_version="1.0.0",
            overlays=overlays,
            resolved_conflicts=tuple(resolved_conflicts),
        )
        primary = dataset_primary if dataset_primary is not None else classified[0]
        # NOTE: design §4.1.1 says `created` / `updated` should reflect the
        # apply timestamp, but apply_promote currently writes this rendered
        # artifact content directly.
        canonical_body = primary.canonical_body
        if kind.kind == "dataset":
            canonical_body = {**primary.project_only_body, **primary.canonical_body}
        canonical_content = _render_canonical(
            canonical_decision,
            canonical_fields=merged,
            canonical_body=canonical_body,
            created=date.today(),
            updated=date.today(),
            kind=kind,
            active_profile=kind.default_profile,
        )
        if kind.kind == "dataset":
            canonical_content = _rewrite_rendered_frontmatter(
                canonical_content,
                {"datapackage": "datapackage.yaml"},
            )
            if dataset_primary_per_resource is None:
                raise PromoteCandidateError(
                    "dataset planning requires discovery datapackage metadata",
                    slug=canonical_case,
                )
            per_resource = dataset_primary_per_resource
            if primary.datapackage_doc is None or primary.datapackage_source_path is None:
                raise PromoteCandidateError(
                    "dataset planning requires discovery datapackage metadata",
                    slug=canonical_case,
                )
            datapackage_content = render_canonical_datapackage_yaml(
                project_doc=primary.datapackage_doc,
                canonical_slug=canonical_case,
                per_resource=per_resource,
            )
            source_hint = _dataset_recipe_source_hint(merged)
            recipe_content = _render_dataset_recipe_stub(
                slug=canonical_case,
                source_hint=source_hint,
            )
            canonical_artifacts = [
                CanonicalArtifact(
                    path=canonical_artifact_path,
                    content=canonical_content,
                    validator="entity-mixin",
                ),
                CanonicalArtifact(
                    path=Path(kind.commons_subdir) / canonical_case / "datapackage.yaml",
                    content=datapackage_content,
                    validator="frictionless-datapackage",
                ),
                CanonicalArtifact(
                    path=Path(kind.commons_subdir) / canonical_case / "recipe" / "README.md",
                    content=recipe_content,
                    validator="plain",
                ),
            ]
            dropped_fields = sorted(
                {
                    field
                    for dropped in dataset_dropped_by_project.values()
                    for field in dropped
                }
            )
            dataset_audit_extras[canonical_case] = {
                "per_resource": per_resource,
                "dropped_fields": dropped_fields,
                "recipe_stubbed": True,
                "override_path": str(primary.datapackage_source_path.parent),
            }
        else:
            canonical_artifacts = [
                CanonicalArtifact(
                    path=canonical_artifact_path,
                    content=canonical_content,
                    validator="entity-mixin",
                )
            ]
        decisions.append(
            PromoteDecision(
                slug=canonical_case,
                canonical_artifacts=canonical_artifacts,
                canonical_version="1.0.0",
                overlays=overlays,
                resolved_conflicts=tuple(resolved_conflicts),
            )
        )

    _validate_plan(decisions)
    return PromotePlan(
        decisions=decisions,
        failed_candidates=soft_failures,
        kind=kind,
        dataset_audit_extras=dataset_audit_extras,
    )


def _validate_plan(decisions: list[PromoteDecision]) -> None:
    """Validate every canonical against its declared base+mixin profile and
    every overlay against overlay-1.1. Raises PromoteValidationError on
    the first failure. Pre-I/O — no disk state mutated.

    Uses `EntityValidator` from science_model.entity_schema:
    - `.validate(entity_dict)` reads the entity's `schema_profile` field and
      composes base + mixin + extensions via the internal SchemaLoader.
    - `.validate_overlay(overlay_dict)` loads overlay-1.1 internally and
      also enforces `id == overlay_of`.
    Both raise `EntityValidationError` on failure.
    """
    from science_model.entity_schema import EntityValidationError, EntityValidator

    for d in decisions:
        for artifact in d.canonical_artifacts:
            _validate_artifact(
                artifact,
                decision_slug=d.slug,
                project_id=None,
            )
        validator = EntityValidator()
        for project_slug, overlay in d.overlays.items():
            overlay_fm = _parse_frontmatter_only(overlay.after_content)
            try:
                validator.validate_overlay(overlay_fm)
            except EntityValidationError as exc:
                raise PromoteValidationError(
                    decision_slug=d.slug,
                    target_kind="overlay",
                    project_id=project_slug,
                    schema_message=str(exc),
                ) from exc


def _validate_artifact(
    artifact: CanonicalArtifact,
    *,
    decision_slug: str,
    project_id: str | None,
) -> None:
    """Plan-time validation dispatch by artifact.validator."""
    if artifact.validator == "plain":
        return
    if artifact.validator == "entity-mixin":
        from science_model.entity_schema import EntityValidator
        from science_model.entity_schema.validator import EntityValidationError

        fm = _parse_frontmatter_only(artifact.content)
        try:
            EntityValidator().validate(fm)
        except EntityValidationError as exc:
            raise PromoteValidationError(
                decision_slug=decision_slug,
                target_kind="canonical",
                project_id=project_id,
                schema_message=str(exc),
            ) from exc
        return
    if artifact.validator == "frictionless-datapackage":
        datapackage = import_module("science_tool.commons.datapackage")
        try:
            parse_canonical_datapackage_yaml = datapackage.parse_canonical_datapackage_yaml
        except AttributeError as exc:
            raise PromoteValidationError(
                decision_slug=decision_slug,
                target_kind="canonical",
                project_id=project_id,
                schema_message=str(exc),
            ) from exc

        try:
            parse_canonical_datapackage_yaml(artifact.content)
        except Exception as exc:
            raise PromoteValidationError(
                decision_slug=decision_slug,
                target_kind="canonical",
                project_id=project_id,
                schema_message=str(exc),
            ) from exc
        return
    raise AssertionError(f"unknown artifact validator: {artifact.validator!r}")


def _commons_is_clean(commons_root: Path, kind: PromoteKindConfig) -> tuple[bool, list[str]]:
    """Path-limited cleanliness check. Untracked files under
    kind.commons_subdir/ or .migrations/ count as dirty."""
    status = _git(commons_root, "status", "--porcelain", "--untracked-files=all").stdout
    dirty: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        flags = line[:2]
        if flags == "??":
            if path.startswith(f"{kind.commons_subdir}/") or path.startswith(".migrations/"):
                dirty.append(path)
        else:
            dirty.append(path)
    return (not dirty, dirty)


def _project_target_files_clean(
    project_root: Path,
    target_filenames: list[str],
    kind: PromoteKindConfig,
) -> tuple[bool, list[str]]:
    """For each filename in `target_filenames`, check whether the overlay
    destination AND every source subdir's same-named file are clean against
    HEAD. The multi-path scan covers the topic flatten case: when a candidate
    came from doc/background/topics/, the apply path unlinks that file, so
    the preflight must catch dirtiness there too."""
    dirty: list[str] = []
    subdirs_to_check = [kind.overlay_dest_subdir, *kind.source_subdirs]
    seen: set[str] = set()
    ordered: list[str] = []
    for subdir in subdirs_to_check:
        if subdir in seen:
            continue
        seen.add(subdir)
        ordered.append(subdir)

    for name in target_filenames:
        for sub in ordered:
            rel = f"{sub}/{name}"
            status = subprocess.run(
                [
                    "git",
                    "-C",
                    str(project_root),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                    "--",
                    rel,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            if status.stdout.strip():
                dirty.append(rel)
    return (not dirty, dirty)


def _project_root_from_overlay_path(path: Path, kind: PromoteKindConfig) -> Path:
    """Derive project root from `<root>/<kind.overlay_dest_subdir>/<file>`."""
    parents_to_strip = len(Path(kind.overlay_dest_subdir).parts) + 1
    return path.parents[parents_to_strip - 1]


def _paths_for_overlay_rollback(rewrite: OverlayRewrite) -> list[Path]:
    paths = [rewrite.path]
    if rewrite.rename_from is not None:
        paths.append(rewrite.rename_from)
    if rewrite.unlinked_source is not None:
        paths.append(rewrite.unlinked_source)
    return list(dict.fromkeys(paths))


def _restore_project_rewrites_to_head(
    rewrites: list[OverlayRewrite],
    kind: PromoteKindConfig,
) -> None:
    """Restore rewritten/unlinked project paths to their pre-apply HEAD state."""
    paths_by_project: dict[Path, list[Path]] = {}
    for rewrite in rewrites:
        project_root = _project_root_from_overlay_path(rewrite.path, kind)
        for path in _paths_for_overlay_rollback(rewrite):
            paths_by_project.setdefault(project_root, []).append(path)

    for project_root, paths in paths_by_project.items():
        for path in dict.fromkeys(paths):
            rel = path.relative_to(project_root)
            existed = (
                subprocess.run(
                    ["git", "-C", str(project_root), "cat-file", "-e", f"HEAD:{rel}"],
                    capture_output=True,
                ).returncode
                == 0
            )
            if existed:
                subprocess.run(
                    ["git", "-C", str(project_root), "checkout", "HEAD", "--", str(rel)],
                    check=True,
                    capture_output=True,
                )
            else:
                path.unlink(missing_ok=True)


def _repo_is_idle(root: Path) -> bool:
    """True if the repo is NOT mid-merge/rebase/cherry-pick/bisect."""
    try:
        git_dir_result = _git(root, "rev-parse", "--git-dir", check=False)
    except OSError:
        return False
    if git_dir_result.returncode != 0:
        return False
    git_dir_raw = git_dir_result.stdout.strip()
    if not git_dir_raw:
        return False
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    sentinels = [
        "MERGE_HEAD",
        "REBASE_HEAD",
        "CHERRY_PICK_HEAD",
        "BISECT_LOG",
        "rebase-apply",
        "rebase-merge",
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
    side_channel_results: dict[str, SideChannelResult] | None = None,
    failure_stage: Literal[
        "preflight",
        "validate",
        "discover",
        "plan",
        "write_commons",
        "side_channel",
        "rewrite_projects",
        "audit",
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
        kind=plan.kind,
        side_channel_results=side_channel_results or {},
        plan_audit_extras=plan.dataset_audit_extras,
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
        logger.error("failure-path audit log write failed for op %s: %s", op_id, audit_exc)
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
            _git(commons_root, "rm", "--cached", "--ignore-unmatch", "--", str(rel), check=False)
            path.unlink(missing_ok=True)


def _resolve_canonical_artifact_path(commons_root: Path, artifact_path: Path) -> Path:
    if artifact_path.is_absolute() or ".." in artifact_path.parts:
        raise PromoteInputError(f"canonical artifact path must be commons-relative: {artifact_path}")

    commons_root_resolved = commons_root.resolve()
    resolved = (commons_root_resolved / artifact_path).resolve(strict=False)
    if not resolved.is_relative_to(commons_root_resolved):
        raise PromoteInputError(f"canonical artifact path escapes commons root: {artifact_path}")
    return resolved


def _audit_failure_detail(failure_detail: str, plan: PromotePlan) -> str:
    detail = failure_detail
    for decision in plan.decisions:
        for artifact in decision.canonical_artifacts:
            if artifact.path.is_absolute() or ".." in artifact.path.parts:
                detail = detail.replace(str(artifact.path), "<invalid canonical artifact path>")
    return detail


def _restore_side_channel_backups(op_id: str) -> None:
    from science_tool.commons.config import restore_data_override_from_backup

    restore_data_override_from_backup(op_id=op_id)


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
    side_channel_results: dict[str, SideChannelResult] = {}
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
            kind=plan.kind,
            plan_audit_extras=plan.dataset_audit_extras,
        )

    try:
        # ---------- Step 0: preflight ----------
        if not commons_root.exists():
            raise PromoteInputError(f"commons store missing at {commons_root}; run `science commons init`")
        commons_root_resolved = commons_root.resolve()
        if not _repo_is_idle(commons_root):
            raise PromoteInputError(f"commons repo is mid-merge/rebase: {commons_root}")
        clean, dirty = _commons_is_clean(commons_root, plan.kind)
        if not clean:
            raise PromoteInputError(
                "commons repo is not clean. Commit/stash before re-running. Dirty: " + ", ".join(dirty)
            )

        target_files_per_project: dict[Path, list[str]] = {}
        rename_collisions: list[tuple[str, Path]] = []
        for decision in plan.decisions:
            for slug, overlay in decision.overlays.items():
                project_root = _project_root_from_overlay_path(overlay.path, plan.kind)
                if overlay.rename_from is not None:
                    target_files_per_project.setdefault(project_root, []).append(overlay.rename_from.name)
                    if overlay.path.exists():
                        rename_collisions.append((slug, overlay.path))
                else:
                    target_files_per_project.setdefault(project_root, []).append(overlay.path.name)
        if rename_collisions:
            raise PromoteInputError(
                "case-rename target(s) already exist on disk: "
                + ", ".join(f"{slug}:{path}" for slug, path in rename_collisions)
            )

        for project_root, names in target_files_per_project.items():
            if not _repo_is_idle(project_root):
                raise PromoteInputError(f"project {project_root} is mid-merge/rebase")
            clean, dirty = _project_target_files_clean(project_root, names, plan.kind)
            if not clean:
                raise PromoteInputError(f"project {project_root} has dirty target files: " + ", ".join(dirty))

        # ---------- Step 5.1: tag preflight ----------
        current_stage = "write_commons"
        for decision in plan.decisions:
            tag = f"{plan.kind.kind}/{decision.slug}/{decision.canonical_version}"
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
        canonical_writes: list[tuple[Path, str]] = []
        for decision in plan.decisions:
            for artifact in decision.canonical_artifacts:
                canonical_writes.append(
                    (
                        _resolve_canonical_artifact_path(commons_root_resolved, artifact.path),
                        artifact.content,
                    )
                )
        try:
            for abs_path, content in canonical_writes:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_text(content, encoding="utf-8")
                written_canonical_paths.append(abs_path)
        except OSError as exc:
            _restore_paths_to_head(commons_root_resolved, written_canonical_paths)
            raise PromoteWriteError(
                stage="write_commons",
                detail=f"commons canonical write failed: {exc}",
            ) from exc

        # ---------- Step 5.2: commit (path-limited) ----------
        rel_paths = [str(p.relative_to(commons_root_resolved)) for p in written_canonical_paths]
        try:
            _git(commons_root, "add", "--", *rel_paths)
            _git(
                commons_root,
                "commit",
                "-m",
                f"promote: {len(plan.decisions)} {plan.kind.commons_subdir} via op {op_id}",
                "--",
                *rel_paths,
            )
        except subprocess.CalledProcessError as exc:
            _restore_paths_to_head(commons_root_resolved, written_canonical_paths)
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
        for decision in sorted(plan.decisions, key=lambda d: d.slug):
            tag = f"{plan.kind.kind}/{decision.slug}/{decision.canonical_version}"
            try:
                _git(commons_root, "tag", tag, commons_commit)
                tags_created.append(tag)
            except subprocess.CalledProcessError as exc:
                _rollback_step5(commons_root_resolved, tags_created, written_canonical_paths)
                rolled_back_commit = commons_commit
                commons_commit = None
                tags_created.clear()
                raise PromoteWriteError(
                    stage="write_commons",
                    detail=(f"tag {tag!r} failed after commit (rolled back {rolled_back_commit}): {exc.stderr or exc}"),
                ) from exc

        # ---------- Step 5.4: side-channel writes ----------
        if plan.kind.side_channel_apply is not None:
            current_stage = "side_channel"
            try:
                for decision in plan.decisions:
                    side_channel_results[decision.slug] = plan.kind.side_channel_apply(
                        SideChannelContext(
                            decision=decision,
                            plan=plan,
                            commons_root=commons_root_resolved,
                            op_id=op_id,
                        )
                    )
            except (OSError, CommonsError) as exc:
                detail = f"side-channel apply failed: {exc}"
                try:
                    _restore_side_channel_backups(op_id)
                except (OSError, CommonsError) as restore_exc:
                    detail += f"; data override restore failed: {restore_exc}"
                _rollback_step5(commons_root_resolved, tags_created, written_canonical_paths)
                rolled_back_commit = commons_commit
                commons_commit = None
                tags_created.clear()
                raise PromoteWriteError(
                    stage="side_channel",
                    detail=f"{detail} (rolled back {rolled_back_commit})",
                ) from exc

        # ---------- Step 6: rewrite projects ----------
        current_stage = "rewrite_projects"
        written_rewrites: list[OverlayRewrite] = []
        current_rewrite: OverlayRewrite | None = None
        try:
            for decision in plan.decisions:
                for slug, overlay in decision.overlays.items():
                    current_rewrite = overlay
                    if slug not in projects_touched:
                        projects_touched.append(slug)
                    if overlay.rename_from is not None and overlay.rename_from.exists():
                        overlay.rename_from.unlink()
                    overlay.path.parent.mkdir(parents=True, exist_ok=True)
                    overlay.path.write_text(overlay.after_content, encoding="utf-8")
                    if overlay.unlinked_source is not None and overlay.unlinked_source != overlay.path:
                        overlay.unlinked_source.unlink()
                    written_rewrites.append(overlay)
                    current_rewrite = None
        except OSError as exc:
            rewrites_to_restore = list(written_rewrites)
            if current_rewrite is not None and current_rewrite not in rewrites_to_restore:
                rewrites_to_restore.append(current_rewrite)
            detail = f"overlay write failed: {exc}"
            try:
                _restore_project_rewrites_to_head(rewrites_to_restore, plan.kind)
            except (OSError, subprocess.CalledProcessError) as restore_exc:
                detail += f"; project rewrite restore failed: {restore_exc}"
            if side_channel_results:
                try:
                    _restore_side_channel_backups(op_id)
                except (OSError, CommonsError) as restore_exc:
                    detail += f"; data override restore failed: {restore_exc}"
                try:
                    _rollback_step5(commons_root_resolved, tags_created, written_canonical_paths)
                    rolled_back_commit = commons_commit
                    commons_commit = None
                    tags_created.clear()
                    detail += f" (rolled back {rolled_back_commit})"
                except (OSError, subprocess.CalledProcessError) as rollback_exc:
                    detail += f"; commons rollback failed: {rollback_exc}"
            raise PromoteWriteError(
                stage="rewrite_projects",
                detail=detail,
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
            kind=plan.kind,
            side_channel_results=side_channel_results,
            plan_audit_extras=plan.dataset_audit_extras,
        )
        try:
            audit_path = _write_audit_log(result, commons_root, invocation=invocation)
        except (OSError, CommonsError) as exc:
            audit_exc = PromoteWriteError(
                stage="audit",
                detail=f"audit log write failed: {exc}",
                commons_commit=commons_commit,
                projects_touched=projects_touched,
            )
            audit_exc.failure_audit_yaml = _render_audit_log_yaml(  # type: ignore[attr-defined]
                result,
                commons_root,
                invocation=invocation,
            )
            raise audit_exc from exc
        try:
            audit_rel = str(audit_path.relative_to(commons_root))
            _git(commons_root, "add", "--", audit_rel)
            _git(commons_root, "commit", "-m", f"audit: op {op_id}", "--", audit_rel)
        except (OSError, subprocess.CalledProcessError) as exc:
            audit_exc = PromoteWriteError(
                stage="audit",
                detail=f"audit log write/commit failed: {exc}",
                commons_commit=commons_commit,
                projects_touched=projects_touched,
            )
            audit_exc.failure_audit_yaml = _render_audit_log_yaml(  # type: ignore[attr-defined]
                result,
                commons_root,
                invocation=invocation,
            )
            raise audit_exc from exc

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
            kind=result.kind,
            side_channel_results=result.side_channel_results,
            plan_audit_extras=result.plan_audit_extras,
        )

    except (PromoteInputError, PromoteWriteError, PromoteCandidateError) as exc:
        if getattr(exc, "stage", None) == "audit" and hasattr(exc, "failure_audit_yaml"):
            raise
        stage = getattr(exc, "stage", None) or current_stage
        audit_path, audit_yaml = _write_failure_audit_log(
            op_id=op_id,
            started_at=started_at,
            commons_root=commons_root,
            commons_commit=commons_commit,
            tags_created=tags_created,
            plan=plan,
            projects_touched=projects_touched,
            side_channel_results=side_channel_results,
            failure_stage=stage,
            failure_detail=_audit_failure_detail(str(exc), plan),
            invocation=invocation,
        )
        if audit_path is None:
            exc.failure_audit_yaml = audit_yaml  # type: ignore[attr-defined]
        raise


# --------------------------------------------------------------------------- #
# Private helpers                                                              #
# --------------------------------------------------------------------------- #

# Sentinel keys for stashing raw frontmatter+body in PromoteCandidate.project_only_body
# during discovery, to be consumed by _classify_entity in plan_promote (Task 11).
# Defined as module-level constants so the coupling between discovery and
# classification is greppable rather than hidden in two string literals.
_RAW_FRONTMATTER_KEY = "__raw_frontmatter__"
_RAW_BODY_KEY = "__raw_body__"


def _normalize_slug_for_match(raw: str, kind: PromoteKindConfig) -> str:
    """Return the matching key for a slug, per kind's `slug_match` policy.

    For paper, casefolds. For topic/theme, returns the stem unchanged and
    asserts the regex (lowercase-only - uppercase letters fail-fast at
    discovery rather than slipping through with silent normalisation).
    """
    stripped = raw.removesuffix(".md").strip()
    if kind.filename_prefix and stripped.startswith(kind.filename_prefix):
        stripped = stripped[len(kind.filename_prefix) :]
    if not stripped:
        raise PromoteCandidateError(f"slug {raw!r} is empty after strip")
    if not kind.slug_regex.match(stripped):
        raise PromoteCandidateError(f"slug {raw!r} does not match {kind.slug_regex.pattern}")
    if kind.slug_match == "casefold":
        return stripped.casefold()
    return stripped


def _classify_file_kind(
    frontmatter: dict,
    kind: PromoteKindConfig,
) -> Literal["match", "skip-other-kind", "skip-other-id"]:
    """Decide whether a file under `kind.source_subdirs` matches this kind.

    Rule order (design §4.1, Phase E §6.3 step 2):
    1. Explicit `kind:` or `type:` equal to `kind.kind` -> match.
    2. Explicit `kind` / `type` with any other value -> skip-other-kind.
    3. No `kind` / `type`, `id` present and NOT starting with `kind.id_prefix` ->
       skip-other-id.
    4. Otherwise infer from directory: match.
    """
    explicit_values = [frontmatter[key] for key in ("kind", "type") if key in frontmatter]
    if any(value == kind.kind for value in explicit_values):
        return "match"
    if explicit_values:
        return "skip-other-kind"
    id_val = frontmatter.get("id")
    if isinstance(id_val, str) and not id_val.startswith(kind.id_prefix):
        return "skip-other-id"
    return "match"


logger = logging.getLogger(__name__)


def _parse_entity_file(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises PromoteCandidateError on
    parse failure, unreadable file, or missing frontmatter delimiters."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PromoteCandidateError(f"unreadable file: {exc}", path=path) from exc
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
        raise PromoteCandidateError(f"frontmatter parse error: {exc}", path=path) from exc
    if not isinstance(fm, dict):
        raise PromoteCandidateError("frontmatter is not a mapping", path=path)
    body = "\n".join(lines[closing_idx + 1 :])
    if text.endswith("\n") and not body.endswith("\n"):
        body += "\n"
    return fm, body


def _parse_frontmatter_only(rendered: str) -> dict:
    """Parse just the frontmatter block from rendered <slug>.md content."""
    if not rendered.startswith("---\n"):
        raise PromoteCandidateError("rendered content has no opening --- fence", slug=None)
    rest = rendered[len("---\n") :]
    end = rest.find("\n---\n")
    if end == -1:
        raise PromoteCandidateError("rendered content has no closing --- fence", slug=None)
    fm_yaml = rest[:end]
    parsed = yaml.safe_load(fm_yaml)
    if not isinstance(parsed, dict):
        raise PromoteCandidateError(f"frontmatter is not a mapping: {type(parsed).__name__}", slug=None)
    return parsed


def _project_relative_path(project_root: Path, value: str, *, field: str) -> Path:
    rel_path = Path(value)
    if rel_path.is_absolute():
        raise PromoteCandidateError(f"{field} path {value!r} must be project-relative")
    root_abs = project_root.resolve()
    abs_path = (root_abs / rel_path).resolve(strict=False)
    try:
        abs_path.relative_to(root_abs)
    except ValueError as exc:
        raise PromoteCandidateError(f"{field} path {value!r} escapes project root") from exc
    return abs_path


def _datapackage_relative_path(datapackage_dir: Path, value: str, *, field: str) -> Path:
    rel_path = Path(value)
    if rel_path.is_absolute():
        raise PromoteCandidateError(f"{field} path {value!r} must be relative to the datapackage")
    package_dir_abs = datapackage_dir.resolve()
    abs_path = (package_dir_abs / rel_path).resolve(strict=False)
    try:
        abs_path.relative_to(package_dir_abs)
    except ValueError as exc:
        raise PromoteCandidateError(f"{field} path {value!r} escapes the datapackage directory") from exc
    return abs_path


def _load_project_datapackage(project_root: Path, datapackage_value: Any) -> tuple[Path, dict[str, Any]]:
    if not isinstance(datapackage_value, str) or not datapackage_value.strip():
        raise PromoteCandidateError("dataset candidate requires a non-empty string datapackage field")

    dp_abs = _project_relative_path(project_root, datapackage_value, field="datapackage")
    if not dp_abs.is_file():
        raise PromoteCandidateError(f"datapackage file does not exist: {datapackage_value}")

    try:
        dp_raw = dp_abs.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PromoteCandidateError(f"datapackage file is unreadable: {exc}") from exc
    try:
        dp_doc = json.loads(dp_raw)
    except json.JSONDecodeError as exc:
        raise PromoteCandidateError(f"datapackage JSON parse error: {exc}") from exc
    if not isinstance(dp_doc, dict):
        raise PromoteCandidateError("datapackage JSON top-level value must be an object")
    resources = dp_doc.get("resources")
    if not isinstance(resources, list):
        raise PromoteCandidateError("datapackage JSON requires resources to be a list")
    return dp_abs, dp_doc


def _resource_name(resource: Mapping[str, Any], resource_path: str) -> str:
    name = resource.get("name")
    if isinstance(name, str) and name:
        return name
    return resource_path


def _validate_datapackage_resources(slug: str, dp_abs: Path, dp_doc: dict[str, Any]) -> None:
    resources = dp_doc["resources"]
    for idx, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise PromoteCandidateError(f"datapackage resources[{idx}] must be an object")
        resource_path = resource.get("path")
        if not isinstance(resource_path, str) or not resource_path.strip():
            raise PromoteCandidateError(f"datapackage resources[{idx}].path must be a non-empty string")
        resource_abs = _datapackage_relative_path(
            dp_abs.parent,
            resource_path,
            field=f"datapackage resources[{idx}].path",
        )
        if not resource_abs.is_file():
            raise PromoteResourceMissingError(
                slug=slug,
                resource_name=_resource_name(resource, resource_path),
                resource_path=Path(resource_path),
            )


def _scan_project(
    project_root: Path,
    project_slug: str,
    kind: PromoteKindConfig,
) -> tuple[list[PromoteCandidate], list[FailedCandidate]]:
    """Walk every dir in kind.source_subdirs and parse each *.md.

    Detects intra-kind same-project collisions (a slug appearing in more
    than one source subdir of the same project — only relevant for topic).
    Calls _classify_file_kind, the eligibility filter (if set), and
    _normalize_slug_for_match. Project-only filenames are mapped to
    `(slug_normalized, source_path)` so the collision check can report
    BOTH offending paths.
    """
    candidates: list[PromoteCandidate] = []
    failures: list[FailedCandidate] = []
    seen: dict[str, tuple[str, Path]] = {}

    for sub in kind.source_subdirs:
        directory = project_root / sub
        if not directory.exists():
            continue
        for source_path in sorted(directory.glob("*.md")):
            if kind.filename_prefix and not source_path.stem.startswith(kind.filename_prefix):
                continue
            try:
                fm, body = _parse_entity_file(source_path)
            except PromoteCandidateError as exc:
                failures.append(
                    FailedCandidate(
                        slug=None,
                        project_slug=project_slug,
                        source_path=source_path,
                        error_class="PromoteCandidateError",
                        error_message=str(exc),
                    )
                )
                continue

            # Skip already-promoted files (overlay_of present).
            if "overlay_of" in fm:
                continue

            classification = _classify_file_kind(fm, kind)
            if classification == "skip-other-kind":
                logger.warning("%s: kind/type is not %r; skipping", source_path, kind.kind)
                continue
            if classification == "skip-other-id":
                continue

            # Eligibility filter (theme only at Phase F).
            if kind.eligibility_filter is not None:
                verdict = kind.eligibility_filter(fm)
                if verdict == EligibilityVerdict.SKIP_SILENT:
                    logger.debug("%s: eligibility skip (kind=%s)", source_path, kind.kind)
                    continue
                if verdict == EligibilityVerdict.FAIL:
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=(
                                f"eligibility filter rejected {source_path.name}: "
                                "missing or malformed eligibility marker"
                            ),
                        )
                    )
                    continue

            # Id check. The classifier may have matched purely on explicit
            # `kind:` / `type:`, while the file also carries a contradictory
            # `id:`. In that case, report failure.
            id_val = fm.get("id")
            if "id" in fm and not isinstance(id_val, str):
                failures.append(
                    FailedCandidate(
                        slug=None,
                        project_slug=project_slug,
                        source_path=source_path,
                        error_class="PromoteCandidateError",
                        error_message=(f"id value {id_val!r} must be a string for kind {kind.kind!r}"),
                    )
                )
                continue
            if kind.slug_from_id and "id" not in fm:
                failures.append(
                    FailedCandidate(
                        slug=None,
                        project_slug=project_slug,
                        source_path=source_path,
                        error_class="PromoteCandidateError",
                        error_message=(f"id is required for kind {kind.kind!r} because slug is derived from id"),
                    )
                )
                continue
            source_case_slug = source_path.stem
            slug_normalized: str | None = None
            id_slug_normalized: str | None = None
            if isinstance(id_val, str):
                if not id_val.startswith(kind.id_prefix):
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=(
                                f"id {id_val!r} does not have the expected "
                                f"prefix {kind.id_prefix!r} for kind "
                                f"{kind.kind!r}"
                            ),
                        )
                    )
                    continue
                id_slug = id_val[len(kind.id_prefix) :]
                try:
                    id_slug_normalized = _normalize_slug_for_match(id_slug, kind)
                except PromoteCandidateError as exc:
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=str(exc),
                        )
                    )
                    continue
                if kind.slug_from_id:
                    slug_normalized = id_slug_normalized
                    source_case_slug = id_slug_normalized

            if slug_normalized is None:
                try:
                    slug_normalized = _normalize_slug_for_match(source_path.stem, kind)
                except PromoteCandidateError as exc:
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=str(exc),
                        )
                    )
                    continue
                if id_slug_normalized is not None and id_slug_normalized != slug_normalized:
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=(f"id {id_val!r} does not match filename stem {source_path.stem!r}"),
                        )
                    )
                    continue

            # Intra-kind same-project collision (topic flatten guard).
            prior = seen.get(slug_normalized)
            if prior is not None and prior[0] != sub:
                _, prior_path = prior
                failures.append(
                    FailedCandidate(
                        slug=slug_normalized,
                        project_slug=project_slug,
                        source_path=source_path,
                        error_class="PromoteCandidateError",
                        error_message=(
                            f"slug {slug_normalized!r} appears in both "
                            f"{prior_path} and {source_path} within project "
                            f"{project_slug!r}; remove one before promoting"
                        ),
                    )
                )
                # Remove the prior candidate so this slug cannot be promoted
                # from a half-resolved same-project corpus.
                candidates[:] = [c for c in candidates if c.slug_normalized != slug_normalized]
                continue

            datapackage_source_path: Path | None = None
            datapackage_doc: dict[str, Any] | None = None
            if kind.kind == "dataset":
                missing_fields = [
                    field
                    for field in ("origin", "tier")
                    if field not in fm or fm[field] in (None, "")
                ]
                origin = fm.get("origin")
                if origin == "external" and ("access" not in fm or fm["access"] in (None, "")):
                    missing_fields.append("access")
                if origin == "derived" and ("derivation" not in fm or fm["derivation"] in (None, "")):
                    missing_fields.append("derivation")
                if missing_fields:
                    for field in missing_fields:
                        failures.append(
                            FailedCandidate(
                                slug=source_case_slug,
                                project_slug=project_slug,
                                source_path=source_path,
                                error_class="PromoteCandidateError",
                                error_message=f"dataset candidate {source_case_slug!r} missing required field {field!r}",
                            )
                        )
                    continue

                try:
                    datapackage_source_path, datapackage_doc = _load_project_datapackage(
                        project_root,
                        fm.get("datapackage"),
                    )
                    _validate_datapackage_resources(
                        source_case_slug,
                        datapackage_source_path,
                        datapackage_doc,
                    )
                except PromoteResourceMissingError as exc:
                    failures.append(
                        FailedCandidate(
                            slug=source_case_slug,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteResourceMissingError",
                            error_message=str(exc),
                        )
                    )
                    continue
                except PromoteCandidateError as exc:
                    failures.append(
                        FailedCandidate(
                            slug=source_case_slug,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=str(exc),
                        )
                    )
                    continue

            seen.setdefault(slug_normalized, (sub, source_path))

            # canonical_fields / project_only_fields / body splits are filled
            # in later by `_classify_entity` (Task 11). For now we stash raw
            # frontmatter + body so discovery is independent of merge-policy
            # lookup.
            candidates.append(
                PromoteCandidate(
                    slug=source_case_slug,
                    slug_normalized=slug_normalized,
                    project_slug=project_slug,
                    project_root=project_root,
                    overlay_source_path=source_path,
                    canonical_fields={},
                    project_only_fields={},
                    canonical_body={},
                    project_only_body={
                        _RAW_FRONTMATTER_KEY: fm,
                        _RAW_BODY_KEY: body,
                    },
                    datapackage_source_path=datapackage_source_path,
                    datapackage_doc=datapackage_doc,
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
_GENERATED_BY_PROMOTE_KEYS: frozenset[str] = frozenset({"schema_profile", "version"})

# Identity fields promote re-derives from the PromoteDecision after the
# canonical slug case is picked. They are stripped from the canonical merge
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
      (after `_pick_canonical_bibkey_case` chooses the canonical-case slug).
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


def _dataset_dropped_fields(
    raw_frontmatter: dict,
    *,
    canonical_fields: dict,
    project_only_fields: dict,
) -> list[str]:
    """Return project frontmatter keys that landed in neither bucket.

    These are keys not recognized by base, dataset mixin, or overlay-1.1 schemas;
    promote drops them silently from output but records them in the audit log.

    Convention: keys starting with `_` are intentional metadata/sentinels and not reported.
    """
    routed = set(canonical_fields) | set(project_only_fields)
    internal = _GENERATED_BY_PROMOTE_KEYS | _PROMOTE_DERIVED_IDENTITY_KEYS | _OVERLAY_ONLY_KEYS
    return sorted(
        k for k in raw_frontmatter if k not in routed and k not in internal and not k.startswith("_")
    )


def _primary_candidate_for_plan(
    candidates: list[PromoteCandidate],
    from_order: list[str],
) -> PromoteCandidate:
    order = {slug: idx for idx, slug in enumerate(from_order)}
    return sorted(
        candidates,
        key=lambda c: (order.get(c.project_slug, len(order)), c.project_slug),
    )[0]


def _project_relative_posix(project_root: Path, path: Path) -> str:
    root_abs = project_root.resolve(strict=False)
    path_abs = path.resolve(strict=False)
    try:
        return path_abs.relative_to(root_abs).as_posix()
    except ValueError as exc:
        raise PromoteCandidateError(f"path {path} escapes project root {project_root}") from exc


def _overlay_target_path(
    candidate: PromoteCandidate,
    *,
    kind: PromoteKindConfig,
    canonical_case: str,
) -> Path:
    filename = f"{canonical_case}.md"
    if kind.kind == "dataset":
        filename = f"{kind.filename_prefix}{canonical_case}.md"
    return candidate.project_root / kind.overlay_dest_subdir / filename


def _dataset_per_resource(candidate: PromoteCandidate) -> dict[str, tuple[str, int]]:
    if candidate.datapackage_source_path is None or candidate.datapackage_doc is None:
        raise PromoteCandidateError(
            "dataset planning requires discovery datapackage metadata",
            slug=candidate.slug,
        )

    per_resource: dict[str, tuple[str, int]] = {}
    dp_parent = candidate.datapackage_source_path.parent
    resources = candidate.datapackage_doc.get("resources")
    if not isinstance(resources, list):
        raise PromoteCandidateError(
            "dataset datapackage resources must be a list",
            slug=candidate.slug,
        )
    for idx, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            raise PromoteCandidateError(
                f"datapackage resources[{idx}] must be an object",
                slug=candidate.slug,
            )
        resource_path = resource.get("path")
        if not isinstance(resource_path, str) or not resource_path.strip():
            raise PromoteCandidateError(
                f"datapackage resources[{idx}].path must be a non-empty string",
                slug=candidate.slug,
            )
        resource_abs = _datapackage_relative_path(
            dp_parent,
            resource_path,
            field=f"datapackage resources[{idx}].path",
        )
        try:
            per_resource[_resource_name(resource, resource_path)] = stream_sha256_and_bytes(
                resource_abs
            )
        except OSError as exc:
            raise PromoteCandidateError(
                f"cannot read datapackage resources[{idx}] bytes: {exc}",
                slug=candidate.slug,
                path=resource_abs,
            ) from exc
    return per_resource


def _validate_dataset_group_datapackages(
    *,
    canonical_slug: str,
    primary: PromoteCandidate,
    candidates: list[PromoteCandidate],
    primary_per_resource: dict[str, tuple[str, int]],
) -> None:
    if len(candidates) <= 1:
        return
    if primary.datapackage_doc is None:
        raise PromoteCandidateError(
            "dataset planning requires discovery datapackage metadata",
            slug=canonical_slug,
        )
    primary_content = render_canonical_datapackage_yaml(
        project_doc=primary.datapackage_doc,
        canonical_slug=canonical_slug,
        per_resource=primary_per_resource,
    )
    for candidate in candidates:
        if candidate is primary:
            continue
        candidate_per_resource = _dataset_per_resource(candidate)
        if candidate_per_resource != primary_per_resource:
            raise PromoteCandidateError(
                f"dataset {canonical_slug!r} project {candidate.project_slug!r} "
                f"has divergent resource hashes/bytes from primary project "
                f"{primary.project_slug!r}",
                slug=canonical_slug,
                path=candidate.datapackage_source_path,
            )
        if candidate.datapackage_doc is None:
            raise PromoteCandidateError(
                "dataset planning requires discovery datapackage metadata",
                slug=canonical_slug,
                path=candidate.datapackage_source_path,
            )
        candidate_content = render_canonical_datapackage_yaml(
            project_doc=candidate.datapackage_doc,
            canonical_slug=canonical_slug,
            per_resource=candidate_per_resource,
        )
        if candidate_content != primary_content:
            raise PromoteCandidateError(
                f"dataset {canonical_slug!r} project {candidate.project_slug!r} "
                f"has divergent canonical datapackage content from primary "
                f"project {primary.project_slug!r}",
                slug=canonical_slug,
                path=candidate.datapackage_source_path,
            )


def _rewrite_rendered_frontmatter(rendered: str, updates: Mapping[str, Any]) -> str:
    if not rendered.startswith("---\n"):
        raise PromoteCandidateError("rendered content has no opening --- fence", slug=None)
    rest = rendered[len("---\n") :]
    fm_raw, sep, body = rest.partition("\n---\n")
    if not sep:
        raise PromoteCandidateError("rendered content has no closing --- fence", slug=None)
    parsed = yaml.safe_load(fm_raw) or {}
    if not isinstance(parsed, dict):
        raise PromoteCandidateError(
            f"frontmatter is not a mapping: {type(parsed).__name__}",
            slug=None,
        )
    parsed.update(updates)
    return f"---\n{_render_frontmatter(parsed)}---\n{body}"


def _dataset_recipe_source_hint(canonical_fields: Mapping[str, Any]) -> str | None:
    sources = canonical_fields.get("sources")
    if isinstance(sources, list) and sources:
        return str(sources[0])
    if isinstance(sources, str) and sources.strip():
        return sources
    source = canonical_fields.get("source")
    if isinstance(source, str) and source.strip():
        return source
    access = canonical_fields.get("access")
    if isinstance(access, Mapping):
        source_url = access.get("source_url")
        if isinstance(source_url, str) and source_url.strip():
            return source_url
    return None


# --------------------------------------------------------------------------- #
# Multi-instance merge helpers (Task 12)                                       #
# --------------------------------------------------------------------------- #


def _merge_canonical_fields(
    candidates: list[PromoteCandidate],
    merge_policy: dict[str, MergePolicy],
    *,
    kind: Literal["paper", "topic", "theme", "dataset"],
) -> tuple[dict, list[FieldConflict]]:
    """Merge canonical_fields across N candidates of the same slug.

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
                    slug=present[0].slug,
                    kind=kind,
                    field=key,
                    candidates={c.project_slug: c.canonical_fields[key] for c in present},
                )
            )

    return merged, conflicts


def _pick_canonical_bibkey_case(
    candidates: list[PromoteCandidate],
    from_order: list[str],
) -> str:
    """Pick the canonical slug case from a multi-instance group.

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
    return sorted_by_order[0].slug


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
                raw = line[len(prefix) :].strip()
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


def _render_dataset_recipe_stub(*, slug: str, source_hint: str | None) -> str:
    src_line = f"Acquisition: {source_hint}." if source_hint else "Acquisition: unspecified."
    return (
        "# Recipe back-fill needed\n\n"
        f"{src_line}\n\n"
        "Promote stubbed this README because no project recipe was detected. "
        "Replace with the acquisition or preprocessing workflow.\n"
    )


def _render_canonical(
    decision: PromoteDecision,
    *,
    canonical_fields: dict,
    canonical_body: dict[str, str],
    created: date,
    updated: date,
    kind: PromoteKindConfig,
    active_profile: "ProfileString",
) -> str:
    """Render the commons-side <commons_subdir>/<slug>.md content.

    Emits schema_profile from `active_profile` (which equals
    `kind.default_profile` for bare promotes, or `kind.default_profile`
    augmented with `--mixin` extensions for Phase H bio promotes). id
    from kind.id_prefix, type from kind.kind. For paper kind only, also
    emits a `bibkey:` field (preserved from Phase E; not in topic/theme
    mixins).
    """
    profile_str = active_profile.render()
    head: dict = {
        "schema_profile": profile_str,
        "id": f"{kind.id_prefix}{decision.slug}",
        "type": kind.kind,
        "title": canonical_fields.get("title", ""),
        "version": decision.canonical_version,
        "created": _coerce_date_for_yaml(created),
        "updated": _coerce_date_for_yaml(updated),
    }
    if kind.kind == "paper":
        head["bibkey"] = decision.slug
    head["tags"] = []
    for k, v in canonical_fields.items():
        if k == "bibkey" and kind.kind != "paper":
            continue
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(canonical_body)
    return f"---\n{fm}---\n{body}"


def _render_overlay(
    decision: PromoteDecision,
    *,
    project_only_fields: dict,
    project_only_body: dict[str, str],
    kind: PromoteKindConfig,
) -> str:
    """Render a project-side overlay file. NEVER emits schema_profile; the
    overlay validator is hardcoded to overlay/1.1 (design §4.4)."""
    head: dict = {
        "id": f"{kind.id_prefix}{decision.slug}",
        "overlay_of": f"{kind.id_prefix}{decision.slug}",
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


def _build_project_rollback_command(
    overlay_rewrites: list[dict],
    kind: PromoteKindConfig,
) -> str:
    """Build a concrete `git checkout HEAD -- <paths>` command for one project,
    given its overlay_rewrites entries from the audit log. Each entry's `path`
    is the absolute target overlay path. Optional `unlinked_source` (flatten
    case) is added to the rollback set so the source-file deletion can also be
    reverted.

    Project root is derived by stripping len(overlay_dest_subdir.parts)+1
    segments from the path (last segment is the file; preceding segments are
    the overlay_dest_subdir).
    """
    if not overlay_rewrites:
        return ""
    first_path = Path(overlay_rewrites[0]["path"])
    parents_to_strip = len(Path(kind.overlay_dest_subdir).parts) + 1
    project_root = first_path.parents[parents_to_strip - 1]

    paths: list[str] = []
    for entry in overlay_rewrites:
        target = Path(entry["path"])
        paths.append(str(target.relative_to(project_root)))
        if "unlinked_source" in entry:
            source = Path(entry["unlinked_source"])
            paths.append(str(source.relative_to(project_root)))
    paths_sorted = sorted(set(paths))
    return f"git -C {project_root} checkout HEAD -- {' '.join(paths_sorted)}"


def _audit_canonical_paths(decision: PromoteDecision, commons_root: Path) -> list[str]:
    paths: list[str] = []
    for artifact in decision.canonical_artifacts:
        try:
            _resolve_canonical_artifact_path(commons_root, artifact.path)
        except PromoteInputError:
            continue
        paths.append(str(artifact.path))
    return paths


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
                "slug": decision.slug,
                "path": str(overlay.path),
                "pin_version": overlay.pin_version,
            }
            if overlay.rename_from is not None:
                entry["rename"] = {
                    "from": overlay.rename_from.name,
                    "to": overlay.path.name,
                }
            unlinked_source = getattr(overlay, "unlinked_source", None)
            if unlinked_source is not None:
                entry["unlinked_source"] = str(unlinked_source)
            projects_touched[slug]["overlay_rewrites"].append(entry)

    log: dict = {
        "op_id": result.op_id,
        "type": result.kind.kind,
        "invocation": invocation,
        "status": result.status,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "commons_commit": result.commons_commit,
        "commons_tags": result.tags_created,
        "projects_touched": projects_touched,
        "decisions": [_audit_decision_entry(d, result, commons_root) for d in result.decisions],
        "conflict_resolutions": [
            {
                "slug": cr.slug,
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
                "slug": f.slug,
                "project_slug": f.project_slug,
                "source_path": str(f.source_path),
                "error_class": f.error_class,
                "error_message": f.error_message,
            }
            for f in result.failed_candidates
        ],
        "rollback": {
            "commons": (f"git -C {commons_root} revert {result.commons_commit}" if result.commons_commit else None),
            # Per design §6.5: each entry is a copy-pasteable git command,
            # not a placeholder. Derive project_root by walking up from each
            # overlay path (`<root>/doc/papers/<file>`) and list every rewritten
            # path so the operator can restore exactly the touched files.
            "projects": {
                slug: _build_project_rollback_command(rewrites["overlay_rewrites"], result.kind)
                for slug, rewrites in projects_touched.items()
            },
        },
    }
    if result.failure_stage:
        log["failure_stage"] = result.failure_stage
        log["failure_detail"] = result.failure_detail

    return yaml.safe_dump(log, sort_keys=False, allow_unicode=True)


def _audit_decision_entry(
    decision: PromoteDecision,
    result: PromoteResult,
    commons_root: Path,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "slug": decision.slug,
        "canonical_version": decision.canonical_version,
        "canonical_paths": _audit_canonical_paths(decision, commons_root),
    }
    if result.kind.kind != "dataset":
        return entry

    extras = result.plan_audit_extras.get(decision.slug, {})
    if not isinstance(extras, Mapping):
        extras = {}
    per_resource = extras.get("per_resource", {})
    if not isinstance(per_resource, Mapping):
        per_resource = {}
    entry["per_resource_hashes"] = {
        str(name): {"hash": str(value[0]), "bytes": value[1]}
        for name, value in per_resource.items()
        if (
            isinstance(value, tuple | list)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], int)
        )
    }
    entry["recipe_stubbed"] = extras.get("recipe_stubbed") is True
    dropped_fields = extras.get("dropped_fields", [])
    if not isinstance(dropped_fields, list | tuple | set):
        dropped_fields = []
    entry["dropped_fields"] = [str(field) for field in dropped_fields]

    side_channel = result.side_channel_results.get(decision.slug)
    if side_channel is not None:
        if side_channel.artifact_paths:
            entry["override_file"] = str(side_channel.artifact_paths[0])
        if side_channel.backup_paths:
            entry["override_backup"] = str(side_channel.backup_paths[0])

    return entry


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
        exists_at_head = _git(commons_root, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0
        if exists_at_head:
            _git(commons_root, "checkout", "HEAD", "--", str(rel))
        else:
            _git(commons_root, "rm", "--cached", "--ignore-unmatch", "--", str(rel), check=False)
            canonical_path.unlink(missing_ok=True)

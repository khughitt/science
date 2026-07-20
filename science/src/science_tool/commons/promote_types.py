"""Shared vocabulary for the promote pipeline.

Every promote layer — discovery, planning, rendering, the git transaction, and the
dataset subsystem — speaks these types. It lives in its own module so those layers
can each import the vocabulary without importing each other.

Nothing here imports from `commons.promote`: this module is the bottom of the DAG.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

from science_tool.commons.promote_body_loss import CanonicalBodyLoss

from science_model.entity_schema import ProfileString
from science_model.entity_schema.profile import ProfileComponent

from science_tool.commons.errors import PromoteInputError


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


# Bio extension classification used by `_validate_mixin_stacking`.
_STRUCTURAL_BIO_EXTENSIONS = frozenset({"bio.matrix", "bio.table"})
_DOMAIN_BIO_EXTENSIONS = frozenset({"bio.rnaseq", "bio.scrna", "bio.cna"})


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
class ExistingCanonicalConflict:
    """A divergence between a source value and an already-committed commons entity.

    Distinct from FieldConflict (which models which contributing project's value wins).
    The source value here may be a merge across several projects, so no source_project.
    """

    slug: str
    kind: Literal["paper", "topic", "theme", "dataset"]
    field: str
    source_value: Any
    existing_value: Any
    existing_version: str
    # What keep-existing would discard from the source's canonical body, counted
    # for the WHOLE entity (not just `field`) because that is the unit the
    # operator's [k]/[a] answer actually decides. fb-2026-07-16-004.
    body_loss: CanonicalBodyLoss | None = None


class _KeepExisting:
    """Sentinel: resolve an ExistingCanonicalConflict by keeping the committed entity."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "KEEP_EXISTING"


KEEP_EXISTING = _KeepExisting()


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
    mode: Literal["mint", "overlay_existing"] = "mint"
    existing_version: str | None = None  # set when mode == "overlay_existing"


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
    mixin_extensions: tuple["ProfileComponent", ...] = ()
    resource_verifications: dict[str, tuple[ResourceVerification, ...]] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class ResourceVerification:
    """One sourced resource's --verify-digests verdict (non-fatal outcomes only).

    `project_slug` disambiguates the same resource `name` appearing in more than
    one project of a multi-project dataset group.
    """

    project_slug: str
    name: str
    status: Literal["verified", "skipped_off_host", "skipped_remote"]
    detail: str


@dataclass(frozen=True, slots=True)
class PerResourceResult:
    """Return type of `_dataset_per_resource`.

    `per_resource` is the unchanged {alias: (hash, bytes)} payload used by
    rendering; `verifications` is empty unless `--verify-digests` is set.
    """

    per_resource: dict[str, tuple[str, int]]
    verifications: tuple[ResourceVerification, ...] = ()


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
    # Project slugs whose source entity file was actually modified by this
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
    mixin_extensions: tuple["ProfileComponent", ...] = ()


def _resolve_canonical_artifact_path(commons_root: Path, artifact_path: Path) -> Path:
    if artifact_path.is_absolute() or ".." in artifact_path.parts:
        raise PromoteInputError(f"canonical artifact path must be commons-relative: {artifact_path}")

    commons_root_resolved = commons_root.resolve()
    resolved = (commons_root_resolved / artifact_path).resolve(strict=False)
    if not resolved.is_relative_to(commons_root_resolved):
        raise PromoteInputError(f"canonical artifact path escapes commons root: {artifact_path}")
    return resolved


# Sentinel keys for stashing raw frontmatter+body in PromoteCandidate.project_only_body
# during discovery, to be consumed by _classify_entity in plan_promote (Task 11).
# Defined as module-level constants so the coupling between discovery and
# classification is greppable rather than hidden in two string literals.
_RAW_FRONTMATTER_KEY = "__raw_frontmatter__"
_RAW_BODY_KEY = "__raw_body__"

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
_PROMOTE_DERIVED_IDENTITY_KEYS: frozenset[str] = frozenset({"id", "kind", "bibkey"})

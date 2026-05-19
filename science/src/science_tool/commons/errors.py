"""Error hierarchy for the commons subpackage."""

from __future__ import annotations

from pathlib import Path
from typing import Literal


class CommonsError(Exception):
    """Base class for all commons-layer errors."""


class CommonsRootNotFoundError(CommonsError):
    """The configured commons store root does not exist on disk."""

    def __init__(self, root: Path) -> None:
        super().__init__(f"commons store not found at {root}; run `science commons init` to create it")
        self.root = root


class CommonsRootMalformedError(CommonsError):
    """The root exists but does not look like a commons store."""

    def __init__(self, root: Path, *, missing: list[str]) -> None:
        super().__init__(f"commons store at {root} is malformed; missing: {', '.join(missing)}")
        self.root = root
        self.missing = missing


class CommonsLayoutError(CommonsError):
    """Filesystem layout invariant violated (e.g., dataset missing datapackage.yaml)."""

    def __init__(self, path: Path, *, reason: str) -> None:
        super().__init__(f"commons layout error at {path}: {reason}")
        self.path = path
        self.reason = reason


class CommonsEntityError(CommonsError):
    """A single entity failed parsing or schema validation."""

    def __init__(
        self,
        path: Path,
        *,
        canonical_id: str | None,
        cause: Exception,
    ) -> None:
        super().__init__(f"commons entity {path} failed: {cause}")
        self.path = path
        self.canonical_id = canonical_id
        self.cause = cause


class CommonsRegistryError(CommonsError):
    """SQLite-level failure (corruption, locked file, schema mismatch)."""

    def __init__(self, db_path: Path, *, cause: Exception) -> None:
        super().__init__(f"commons registry at {db_path} failed: {cause}")
        self.db_path = db_path
        self.cause = cause


class CommonsDatapackageError(CommonsError):
    """A datapackage.yaml is malformed, missing resources[], has an invalid or
    duplicate resource path, or has a resource with a missing/malformed hash."""

    def __init__(self, path: Path, *, reason: str) -> None:
        super().__init__(f"commons datapackage error at {path}: {reason}")
        self.path = path
        self.reason = reason


class DataLogicalPathError(CommonsError):
    """A logical path string is not a safe forward-slash relative path.

    Carries the offending string (not a Path) so a bad CLI argument is not
    forced to masquerade as a datapackage file.
    """

    def __init__(self, logical_path: str, *, reason: str) -> None:
        super().__init__(f"invalid logical path {logical_path!r}: {reason}")
        self.logical_path = logical_path
        self.reason = reason


class DataResourceNotFoundError(CommonsError):
    """The bytes for a resource were not found in any lookup source."""

    def __init__(self, dataset_id: str, logical_path: str, *, tried: list[Path]) -> None:
        tried_str = ", ".join(str(p) for p in tried)
        super().__init__(f"data resource {dataset_id} / {logical_path} not found; tried: {tried_str}")
        self.dataset_id = dataset_id
        self.logical_path = logical_path
        self.tried = tried


class DataIntegrityError(CommonsError):
    """A resource file was found but its sha256 does not match the expected hash."""

    def __init__(self, path: Path, *, expected: str, actual: str) -> None:
        super().__init__(f"data integrity error at {path}: expected {expected}, got {actual}")
        self.path = path
        self.expected = expected
        self.actual = actual


class ProjectNotRegisteredError(CommonsError):
    """A `--project <name>` value has no entry in config.yaml `projects[]`."""

    def __init__(self, name: str) -> None:
        super().__init__(f"project {name!r} is not registered; check `projects:` in the global config")
        self.name = name


class ProjectDirectoryMissingError(CommonsError):
    """A registered project's path is not a directory on disk."""

    def __init__(self, project: str, path: Path) -> None:
        super().__init__(f"registered project {project!r} directory not found at {path}")
        self.project = project
        self.path = path


class OverlayValidationError(CommonsError):
    """A project overlay file failed parsing or schema validation, or its
    `overlay_of` does not resolve to a real canonical entity."""

    def __init__(
        self,
        overlay_path: Path,
        *,
        canonical_id: str | None,
        cause: Exception,
    ) -> None:
        super().__init__(f"overlay {overlay_path} failed: {cause}")
        self.overlay_path = overlay_path
        self.canonical_id = canonical_id
        self.cause = cause


class OverlayMergeError(CommonsError):
    """Defense-in-depth: a `replace`/`forbidden` field reached `merge_entity`
    despite overlay-schema validation. Indicates a corrupt overlay schema or a
    validation bypass, never a normal user path."""

    def __init__(self, *, field: str, canonical_id: str) -> None:
        super().__init__(
            f"overlay for {canonical_id} sets field {field!r} whose merge policy forbids overlay contribution"
        )
        self.field = field
        self.canonical_id = canonical_id


class PromoteInputError(CommonsError):
    """Bad input to `science commons promote`.

    Raised for: missing/unregistered/null-id `--from` slug; commons store missing;
    required positional argument absent; dirty target file at preflight; commons
    repo dirty at preflight; repo mid-merge/rebase/cherry-pick/bisect.
    """


class PromoteMixinStackingError(PromoteInputError):
    """`--mixin` flag violated the stacking rule (more than one structural
    mixin, or more than one domain mixin).

    Intended for Phase H paths in both the CLI parse path and plan_promote so
    direct Python callers cannot bypass the rule.
    """


class PromoteMixinResolutionError(PromoteInputError):
    """`--mixin` could not be resolved to an installed bio extension schema.

    Intended for Phase H resolution paths, unified for operator UX:
    - Sugar form (`--mixin bio.bogus`): no `extension-bio-bogus-*.json` on disk.
    - Explicit form (`--mixin bio.bogus/1.0`): SchemaNotFoundError surfaces
      during `plan_promote`'s `read_merge_policy(active_profile)` setup and
      is caught + rewrapped there.
    - `_validate_artifact` can use the same exception path as a
      belt-and-suspenders guard for already-rendered canonical content that
      cites a missing extension.
    """


class PromoteCandidateError(CommonsError):
    """A promotion candidate file is malformed (parse error, unreadable, schema-failing).

    Constructed per-candidate. NOT raised out of `discover_candidates`;
    instead wrapped as a `FailedCandidate` in the plan. Raised directly only by
    `apply_promote` if an in-plan decision turns out to be unparseable at write
    time (file deleted between plan and apply) — that's a hard-stop case.
    """

    def __init__(
        self,
        message: str,
        *,
        slug: str | None = None,
        path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.slug = slug
        self.path = path


class PromoteResourceMissingError(CommonsError):
    """A resources[].path entry in a project datapackage doesn't resolve.

    Recorded as a FailedCandidate during discovery; does not abort the run.
    """

    def __init__(
        self,
        *,
        slug: str,
        resource_name: str,
        resource_path: Path,
    ) -> None:
        self.slug = slug
        self.resource_name = resource_name
        self.resource_path = resource_path
        super().__init__(
            f"dataset {slug!r}: resource {resource_name!r} at "
            f"{resource_path} does not exist"
        )


class PromoteValidationError(CommonsError):
    """Canonical content or an overlay failed schema validation at the end
    of `plan_promote`. Raised BEFORE any I/O — no rollback needed.

    Carries `decision_slug` (the slug whose plan triggered the failure),
    `target_kind` ("canonical" or "overlay"), `project_id` (overlay only —
    which project's overlay failed), and `schema_message` (the underlying
    jsonschema error string).
    """

    def __init__(
        self,
        *,
        decision_slug: str,
        target_kind: Literal["canonical", "overlay"],
        project_id: str | None,
        schema_message: str,
    ) -> None:
        scope = (
            f"{target_kind}"
            if project_id is None
            else f"{target_kind} in project {project_id!r}"
        )
        super().__init__(
            f"plan-time validation failed for {decision_slug!r} ({scope}): "
            f"{schema_message}"
        )
        self.decision_slug = decision_slug
        self.target_kind = target_kind
        self.project_id = project_id
        self.schema_message = schema_message


class PromoteConflictAbort(CommonsError):
    """User aborted at a conflict prompt (Ctrl-C, or 'abort' answer).

    Batch stops cleanly before any commons or project write.
    """


class PromoteOverrideConflictError(CommonsError):
    """A planned dataset override conflicts with an existing target path."""

    def __init__(
        self,
        *,
        slug: str,
        existing_path: Path,
        planned_path: Path,
    ) -> None:
        super().__init__(
            f"dataset {slug!r} override conflicts: "
            f"existing path {existing_path} differs from planned path {planned_path}"
        )
        self.slug = slug
        self.existing_path = existing_path
        self.planned_path = planned_path


class PromoteWriteError(CommonsError):
    """IO / git failure during apply steps 4–7.

    Carries `stage`, `detail`, and optional partial-state info (commons commit
    hash if step 5 landed, list of projects touched) so the audit log can record
    exactly what landed.
    """

    def __init__(
        self,
        *,
        stage: str,
        detail: str,
        commons_commit: str | None = None,
        projects_touched: list[str] | None = None,
    ) -> None:
        super().__init__(f"[{stage}] {detail}")
        self.stage = stage
        self.detail = detail
        self.commons_commit = commons_commit
        self.projects_touched = projects_touched or []

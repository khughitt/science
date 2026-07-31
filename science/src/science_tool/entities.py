from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError
from science_model.entities import OriginRecord, ProjectEntity
from science_model.entity_schema import (
    PROJECT_MIXIN_NAMES,
    EntityValidationError,
    check_resolution,
    has_lineage_to_resolve,
)
from science_model.frontmatter import atomic_write_text, split_frontmatter
from science_model.profiles import EntityKind, ProfileManifest, load_profile_manifest
from science_model.profiles.schema import EntityFilenameStrategy

from science_tool.entity_profiles import load_project_schema_if_pinned
from science_tool.entity_scan import iter_entity_markdown
from science_tool.kind_descriptors import DECLARED_STATUSES, KIND_DESCRIPTORS
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.migrate import AuditRow, audit_project_sources
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import (
    AliasCollisionError,
    ProjectSources,
    load_project_sources,
    local_profile_sources_dir,
    resolve_local_profile_name,
)
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
from science_tool.project_walk import iter_project_files

LOCAL_PART_WIDTH = 4


class EntityCommandError(ValueError):
    """Raised for user-correctable entity CLI errors."""


@dataclass(frozen=True)
class EntityPathPolicy:
    root: Path
    strategy: EntityFilenameStrategy


_KIND_DESCRIPTORS = KIND_DESCRIPTORS

_BUILTIN_MARKDOWN_POLICIES: dict[str, EntityPathPolicy] = {
    ek.name: EntityPathPolicy(Path(ek.home), cast(EntityFilenameStrategy, ek.strategy))
    for ek in _KIND_DESCRIPTORS
    if ek.home is not None and ek.strategy is not None
}
# Cache local-policy reads keyed by (project_root, manifest mtime_ns) so repeated
# resolve_path_policy calls during a migration don't re-parse the manifest, while
# still picking up edits (important for tests that rewrite the manifest).
_LOCAL_POLICY_CACHE: dict[tuple[str, int], tuple[dict[str, EntityPathPolicy], list[tuple[str, str]]]] = {}

# Parsed-manifest cache (mtime-keyed, mirrors _LOCAL_POLICY_CACHE) so the status
# accessors don't re-parse the manifest on every call during synthesis.
_LOCAL_MANIFEST_CACHE: dict[tuple[str, int], ProfileManifest | None] = {}

# Strategies a local kind may declare. `singleton` is intentionally excluded:
# the migrator's singleton handling (`_plan_singletons`) is hard-coded to the two
# core singleton paths and has no local-singleton semantics, so a local singleton
# would be accepted, discovered, then never moved. Forbid it fail-loud here.
_VALID_STRATEGIES: frozenset[str] = frozenset({"numeric", "citekey", "slug", "id-local"})

# Set of directory (or file) names that belong to core kinds' homes.  A local
# kind whose resolved home has the same final path component would silently
# overwrite the core entry in a dir→kind inference map.  Computed once at
# import time from the authoritative builtin table.
_CORE_HOME_DIR_NAMES: frozenset[str] = frozenset(policy.root.name for policy in _BUILTIN_MARKDOWN_POLICIES.values())


def _resolve_local_home(name: str, home: str | None) -> Path:
    """Resolve (and validate) a local kind's home directory.

    Default is ``entities/<name>``. An explicit ``home`` override must be a
    *relative* path of at least two segments rooted at ``entities/`` with no
    parent traversal — anything else (absolute, ``../``, a non-``entities/``
    root, or the bare ``entities`` root itself) is rejected fail-loud. This keeps
    migration writes inside a dedicated ``entities/<segment>/`` subdirectory and
    prevents a kind's home from scanning top-level ``entities/*.md`` (which would
    swallow core singleton markdown).
    """
    if not home:
        return Path(f"entities/{name}")
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


def _load_local_policies_and_warnings(
    project_root: Path,
) -> tuple[dict[str, EntityPathPolicy], list[tuple[str, str]]]:
    """Load local markdown-kind policies, skipping (not raising on) malformed
    kinds. Returns (policies, kind_warnings) where kind_warnings is a list of
    (kind_name, reason) for every kind dropped during validation. Cached on the
    manifest mtime exactly as the prior single-dict implementation was."""
    profile_name = resolve_local_profile_name(project_root)
    manifest_path = local_profile_sources_dir(project_root, local_profile=profile_name) / "manifest.yaml"
    if not manifest_path.is_file():
        return {}, []
    cache_key = (str(manifest_path), manifest_path.stat().st_mtime_ns)
    cached = _LOCAL_POLICY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    manifest = load_profile_manifest(manifest_path)
    result = derive_local_entity_policies(manifest)
    _LOCAL_POLICY_CACHE[cache_key] = result
    return result


def derive_local_entity_policies(
    manifest: ProfileManifest | None,
) -> tuple[dict[str, EntityPathPolicy], list[tuple[str, str]]]:
    """Derive admissible local markdown policies from a parsed manifest.

    The function performs no filesystem I/O. Pathname loaders and descriptor-safe
    readers pass the same validated model through this one policy authority.
    """
    policies: dict[str, EntityPathPolicy] = {}
    kind_warnings: list[tuple[str, str]] = []
    if manifest is not None:
        for ek in manifest.entity_kinds:
            if ek.name != ek.canonical_prefix:
                kind_warnings.append(
                    (ek.name, f"canonical_prefix {ek.canonical_prefix!r} != name {ek.name!r}; skipped")
                )
                continue
            if ek.name in _BUILTIN_MARKDOWN_POLICIES:
                continue  # a local kind may not shadow a core kind (silent, core wins)
            if ek.strategy is not None and ek.strategy not in _VALID_STRATEGIES:
                kind_warnings.append(
                    (ek.name, f"strategy {ek.strategy!r} not one of {sorted(_VALID_STRATEGIES)}; skipped")
                )
                continue
            try:
                root = _resolve_local_home(ek.name, ek.home)
            except EntityCommandError as exc:
                kind_warnings.append((ek.name, f"{exc}; skipped"))
                continue
            if root.name in _CORE_HOME_DIR_NAMES:
                kind_warnings.append(
                    (ek.name, f"home {root!r} collides with core entity directory {root.name!r}; skipped")
                )
                continue
            strategy = cast(EntityFilenameStrategy, ek.strategy or "numeric")
            policies[ek.name] = EntityPathPolicy(root, strategy)
    return policies, kind_warnings


def load_local_entity_policies(project_root: Path) -> dict[str, EntityPathPolicy]:
    """Path policies for the project's registered local markdown kinds.

    Malformed kinds (bad canonical_prefix/home/strategy, or a home colliding with
    a core directory) are skipped; see `local_kind_warnings` for the reasons. This
    preserves the dict signature every caller relies on (notably `entity_policies`,
    which splats `{**load_local_entity_policies(...), **builtins}`)."""
    return _load_local_policies_and_warnings(project_root)[0]


def local_kind_warnings(project_root: Path) -> list[tuple[str, str]]:
    """The (kind_name, reason) pairs for local kinds skipped during policy load."""
    return _load_local_policies_and_warnings(project_root)[1]


def entity_policies(project_root: Path | None = None) -> dict[str, EntityPathPolicy]:
    """Return the path-policy table: core builtins only, or builtins ∪ local kinds
    when *project_root* is supplied. Builtins always win on name collision."""
    if project_root is None:
        return dict(_BUILTIN_MARKDOWN_POLICIES)
    return {**load_local_entity_policies(project_root), **_BUILTIN_MARKDOWN_POLICIES}


_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
# `verbatim` preserves a sequence-style local part exactly (e.g. decision ids
# D1, D2-treatment-response-category). Unlike `slug` it is case-preserving and
# never derived. Path-safety: no slash, no leading dot, no `..`.
_VERBATIM_RE = re.compile(r"^(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._-]*$")
_CITEKEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.-]*$")
_NUMERIC_LOCAL_PART_RE = re.compile(r"^\d{4}-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_ID_PREFIX_RE = re.compile(r"^(?P<prefix>[a-z]?)(?P<number>\d+)-", re.IGNORECASE)
_NUMERIC_SCAN_RE = re.compile(r"^(?:[A-Za-z])?(\d+)")
_SHORTFORM_REF_RE = re.compile(r"^(?P<prefix>[A-Za-z])(?P<number>\d+)(?P<suffix>(?:[.-].*)?)$")
_NOTES_HEADING_RE = re.compile(r"^##\s+Notes\s*$")
_SHORTFORM_ENTITY_KINDS: dict[str, str] = {ek.shortform: ek.name for ek in _KIND_DESCRIPTORS if ek.shortform}
_DEFAULT_STATUS: dict[str, str] = {ek.name: ek.default_status for ek in _KIND_DESCRIPTORS if ek.default_status}
_STATUS_VALUES: dict[str, frozenset[str]] = DECLARED_STATUSES
_EXTRA_FRONTMATTER_RESERVED_KEYS = frozenset(
    {"id", "kind", "title", "status", "related", "source_refs", "created", "updated"}
)
_ALLOWED_EXPLICIT_ROOTS = (Path("entities"),)

# Lifecycle states hidden from default view/consumer surfaces (consolidation P1).
# `archived` is reserved here for forward-compatibility; nothing sets it until the
# archive/apply phases. Filtering happens at consumer layers ONLY — never at the
# KG ingestion layer (MarkdownAdapter.discover / load_project_sources), so
# `sci:supersedes` lineage survives materialization.
_HIDDEN_STATUSES: frozenset[str] = frozenset({"superseded", "archived"})

# CLOSED: no longer an object of active work. A THIRD axis, and not a synonym for either set
# around it -- `retired` and `complete` are CLOSED but still default-VISIBLE (hidden and closed are
# different questions), and `active` is open whatever the evidence says.
#
# This is the set `disposition: closed` used to name, and it is the whole reason that field could be
# deleted rather than migrated: closure is a LIFECYCLE fact, so once `status` carries the lifecycle,
# a second field for it is the collapse re-introduced under a new name. Every consumer that asked
# "is this still being worked?" -- attention ranking, re-homing debt, demand closure -- asks it here,
# and asks it in ONE place, because three copies of a vocabulary is how they drift.
#
# ☠️ NOT `refuted`. A refuted hypothesis is very often still being worked (written up, probed for
# why), which is precisely why the verdict and the lifecycle are two fields. Closure is something a
# person DID; a verdict is what the evidence SAYS. Reading one off the other is the bug this arc
# exists to end.
CLOSED_LIFECYCLE_STATUSES: frozenset[str] = frozenset(
    {"complete", "superseded", "retired", "archived", "abandoned", "deprecated"}
)

# Human-curated allowlist of statuses that remain default-visible. This is the
# source of truth the EntityKind schema lacks (it carries only `statuses` /
# `default_status`, no live/terminal metadata). Every status declared by any core
# kind must appear here or in `_HIDDEN_STATUSES`; the guard tests in
# test_status_visibility.py fail loud on an unclassified status, forcing a
# deliberate live-or-hidden decision when a new status is introduced. Per design
# open-question #5, `retired`/`deprecated`/`abandoned` stay LIVE (visible) in this
# slice — no regression vs today.
_LIVE_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "active",
        "retired",
        "partially-answered",
        "answered",
        "deferred",
        # `proposed` is the DATASET lifecycle's, and `supported`/`weakened`/`contested` are the
        # PROPOSITION's. They were also the hypothesis VERDICT vocabulary, worn as a status --
        # and they stay here only because those other kinds still declare them as statuses.
        # `under-investigation`, `partially-supported` and `refuted` are gone with the collapse:
        # no kind declares them now, and the first two were never anything but "the evidence has
        # not spoken", which `verdict`'s ABSENCE says without a word for it.
        "proposed",
        "supported",
        "weakened",
        "complete",
        "contested",
        # Pre-registration lifecycle. `committed` is the freeze point -- emphatically
        # LIVE: a committed pre-registration is the one thing a study must not lose
        # sight of.
        "committed",
        "amended",
        "deprecated",
        "abandoned",
        # Story lifecycle (Phase 3b: story kind wired for entity create).
        "developing",
        "mature",
        # Adapter-backed kinds (dataset/workflow/workflow-run/workflow-step), wired
        # in the 2026-06-21 adapter-entity-layout migration. All are live lifecycle
        # states (superseded is already hidden above).
        "candidate",
        "planned",
        "running",
        "failed",
        "pending",
    }
)


def _local_entity_kind(project_root: Path, kind: str) -> EntityKind | None:
    """Return the manifest EntityKind for a local kind, or None."""
    profile_name = resolve_local_profile_name(project_root)
    manifest_path = local_profile_sources_dir(project_root, local_profile=profile_name) / "manifest.yaml"
    if not manifest_path.is_file():
        return None
    cache_key = (str(manifest_path), manifest_path.stat().st_mtime_ns)
    if cache_key not in _LOCAL_MANIFEST_CACHE:
        _LOCAL_MANIFEST_CACHE[cache_key] = load_profile_manifest(manifest_path)
    manifest = _LOCAL_MANIFEST_CACHE[cache_key]
    if manifest is None:
        return None
    return next((ek for ek in manifest.entity_kinds if ek.name == kind), None)


def default_status(kind: str, *, project_root: Path | None = None) -> str:
    """The per-kind default status (e.g. hypothesis → 'proposed')."""
    if kind in _DEFAULT_STATUS:
        return _DEFAULT_STATUS[kind]
    if project_root is not None:
        ek = _local_entity_kind(project_root, kind)
        if ek is not None:
            return ek.default_status or "active"
    raise KeyError(kind)


def valid_statuses(kind: str, *, project_root: Path | None = None) -> frozenset[str] | None:
    """The controlled status set for `kind`, or None for a local kind with no
    declared vocabulary (an open set — any status accepted)."""
    if kind in _STATUS_VALUES:
        return _STATUS_VALUES[kind]
    if project_root is not None:
        ek = _local_entity_kind(project_root, kind)
        if ek is not None:
            return frozenset(ek.statuses) if ek.statuses else None
    raise KeyError(kind)


def is_default_visible(status: str | None) -> bool:
    """Whether an entity with ``status`` is shown by default on view/consumer
    surfaces. A missing/empty status is visible; only explicitly hidden lifecycle
    states (`_HIDDEN_STATUSES`) are excluded. This is NOT ``status == "active"`` —
    live statuses such as `proposed`, `answered`, `complete`, `retired` stay
    visible.
    """
    return status not in _HIDDEN_STATUSES


@dataclass(frozen=True)
class EntityWriteResult:
    entity_id: str
    path: Path
    warnings: list[str]


@dataclass(frozen=True)
class EntityLocation:
    entity_id: str
    kind: str
    title: str
    status: str
    path: Path
    rel_path: str
    frontmatter: dict[str, object]
    body: str


@dataclass(frozen=True)
class EntityReferenceHit:
    path: Path
    rel_path: str
    line: int
    kind: str
    detail: str


@dataclass(frozen=True)
class EntityRemovalPlan:
    entity_id: str
    path: Path
    rel_path: str
    safe_hits: list[EntityReferenceHit]
    manual_hits: list[EntityReferenceHit]


def resolve_path_policy(kind: str, *, project_root: Path | None = None) -> EntityPathPolicy:
    try:
        return entity_policies(project_root)[kind]
    except KeyError as exc:
        raise EntityCommandError(f"Unsupported source-authored entity kind: {kind}") from exc


def markdown_entity_kinds(project_root: Path | None = None) -> tuple[str, ...]:
    """All kinds the policy table governs (core, plus local when project-scoped)."""
    return tuple(entity_policies(project_root))


def is_markdown_entity_kind(kind: str, *, project_root: Path | None = None) -> bool:
    return kind in entity_policies(project_root)


def local_part_conforms(kind: str, local_part: str, *, project_root: Path | None = None) -> bool:
    """True iff ``local_part`` matches the kind's filename strategy."""
    strategy = resolve_path_policy(kind, project_root=project_root).strategy
    if strategy == "numeric":
        return bool(_NUMERIC_LOCAL_PART_RE.fullmatch(local_part))
    if strategy == "citekey":
        return bool(_CITEKEY_RE.fullmatch(local_part))
    if strategy in ("slug", "id-local"):
        # id-local local parts are slug-shaped (the id is authoritative; only the
        # migrator treats it specially by deriving the filename from the id).
        return bool(_SLUG_RE.fullmatch(local_part))
    if strategy == "verbatim":
        return bool(_VERBATIM_RE.fullmatch(local_part))
    return False  # singletons have no per-instance local part


def singleton_path(kind: str) -> Path:
    policy = resolve_path_policy(kind)
    if policy.strategy != "singleton":
        raise EntityCommandError(f"{kind} is not a singleton kind")
    return policy.root


def truncate_slug_on_word_boundary(slug: str, max_length: int) -> str:
    """Cap a kebab-case slug at ``max_length`` without cutting mid-word.

    A plain ``slug[:max_length]`` can leave a partial trailing token
    (e.g. ``"...-dysregulation-express"``). When the cap falls inside a token,
    back up to the previous hyphen so the slug ends on a whole word. Fall back
    to a hard cut only when there is no interior boundary to back up to — a
    single token longer than ``max_length`` cannot be split.
    """
    if len(slug) <= max_length:
        return slug
    if slug[max_length] != "-":
        boundary = slug.rfind("-", 0, max_length)
        if boundary >= 2:
            return slug[:boundary]
    return slug[:max_length].rstrip("-")


DERIVED_SLUG_MAX_LENGTH = 72


def normalize_to_slug(title: str) -> str:
    """Kebab-case a title without applying the length cap."""
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")


def slug_from_raw(raw: str) -> str:
    """Normalize + word-boundary-truncate a raw string to an entity slug (no length guard)."""
    return truncate_slug_on_word_boundary(normalize_to_slug(raw), DERIVED_SLUG_MAX_LENGTH)


def slug_for_claim_text(claim: str) -> str:
    """Deterministic proposition slug from a claim sentence; fail loud if it can't form one."""
    slug = slug_from_raw(claim)
    if len(slug) < 2:
        raise EntityCommandError("claim text cannot derive a stable proposition slug; set an explicit id")
    return slug


def render_entity_text(
    entity: Any,  # any typed entity exposing .kind, .id, and Pydantic .model_dump()
    *,
    body: str,
    created: str,
    updated: str,
) -> str:
    """Render a typed entity Markdown file with caller-selected dates and body."""
    kind = entity.kind
    assert entity.id is not None
    frontmatter = entity.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
    frontmatter["id"] = entity.id
    frontmatter["kind"] = kind
    frontmatter.setdefault("status", default_status(kind))
    for derived in ("canonical_id", "content_preview", "content", "file_path", "type"):
        frontmatter.pop(derived, None)
    frontmatter["created"] = created
    frontmatter["updated"] = updated
    return _render_markdown(frontmatter, body)


def render_entity_source_refs(
    file_path: Path,
    refs_to_append: Sequence[str],
    *,
    as_of: date | None = None,
) -> tuple[str, bool]:
    """Return rendered entity markdown after appending missing source refs.

    Existing refs keep their current order, new refs are appended in
    caller-provided order, exact strings are deduped, and updated advances only
    when the rendered content changes.
    """
    frontmatter, body = _parse_markdown_file_preserving_body(file_path)
    refs = list(frontmatter.get("source_refs") or [])
    changed = False
    for ref in refs_to_append:
        if ref in refs:
            continue
        refs.append(ref)
        changed = True
    if not changed:
        return (file_path.read_text(encoding="utf-8"), False)
    frontmatter["source_refs"] = refs
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    return (_render_markdown(frontmatter, body), True)


def render_entity_frontmatter_updates(
    file_path: Path,
    updates: Mapping[str, object],
    *,
    as_of: date | None = None,
) -> tuple[str, bool]:
    """Return rendered entity markdown after applying exact frontmatter updates."""
    frontmatter, body = _parse_markdown_file_preserving_body(file_path)
    changed = False
    for key, value in updates.items():
        if frontmatter.get(key) == value:
            continue
        frontmatter[key] = value
        changed = True
    if not changed:
        return (file_path.read_text(encoding="utf-8"), False)
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    return (_render_markdown(frontmatter, body), True)


def append_entity_source_ref(file_path: Path, ref: str, *, as_of: date | None = None) -> bool:
    """Append ``ref`` to an existing entity file's ``source_refs`` frontmatter, preserving
    the body. Returns True if added, False if already present. Used by promotion LINK so a
    hand-authored proposition's prose is never clobbered. When a ref is added, `updated`
    advances to ``as_of`` (or today), matching other entity mutations."""
    rendered, changed = render_entity_source_refs(file_path, [ref], as_of=as_of)
    if not changed:
        return False
    _atomic_replace_text(file_path, rendered)
    return True


def derive_slug(title: str) -> str:
    slug = truncate_slug_on_word_boundary(normalize_to_slug(title), DERIVED_SLUG_MAX_LENGTH)
    if len(slug) < 2:
        raise EntityCommandError("Title cannot derive a stable slug; requires --slug")
    return validate_slug(slug)


def validate_slug(slug: str) -> str:
    if len(slug) < 2 or not _SLUG_RE.fullmatch(slug):
        raise EntityCommandError(f"Invalid slug: {slug}")
    return slug


def resolve_entity_slug(title: str, slug: str | None) -> str:
    """The slug ``create_entity`` will use for ``(title, slug)``, or raise.

    Rejects an invalid explicit slug, and a title whose auto-derived slug would
    lose its discriminating tail to the length cap. Every naming failure
    ``create_entity`` can raise before touching the filesystem is decidable
    here, from the title alone — so a caller creating many entities in a loop
    calls this for each planned create up front, and a predictable naming
    failure aborts the batch instead of stranding it half-written.
    """
    if slug is not None:
        return validate_slug(slug)
    full_slug = normalize_to_slug(title)
    used_slug = truncate_slug_on_word_boundary(full_slug, DERIVED_SLUG_MAX_LENGTH)
    if used_slug != full_slug:
        # Fail early rather than write a file whose auto-derived id silently
        # drops the discriminating tail of the title. The remediation is
        # actionable only before the write, not after (the caller would
        # otherwise have to rm + recreate). (fb-2026-07-19-015, superseding the
        # warn-after-write of fb-2026-05-30-012.)
        dropped = full_slug[len(used_slug) :].lstrip("-")
        raise EntityCommandError(
            f"Title is too long to derive a safe id slug: truncation would drop "
            f"'{dropped}' from the id, losing the discriminating tail. Set an explicit "
            f"slug (--slug on the CLI, 'slug:' in an exploration report block), "
            f"e.g. '{used_slug}'."
        )
    return derive_slug(title)


def validate_entity_id(kind: str, entity_id: str) -> str:
    prefix = f"{kind}:"
    if entity_id.startswith(prefix):
        local_part = entity_id[len(prefix) :]
    elif ":" in entity_id:
        raise EntityCommandError(f"Entity id must use prefix {prefix}")
    else:
        local_part = entity_id
        entity_id = f"{prefix}{local_part}"
    strategy = resolve_path_policy(kind).strategy
    if strategy == "singleton":
        raise EntityCommandError(f"{kind} is a singleton and has no per-instance id")
    if strategy == "citekey":
        if not _CITEKEY_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid citekey local part: {entity_id}")
        return entity_id
    if strategy in ("slug", "id-local"):
        if not _SLUG_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid slug local part: {entity_id}")
        return entity_id
    if strategy == "verbatim":
        if not _VERBATIM_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid verbatim local part: {entity_id}")
        return entity_id
    # numeric: an explicit --id must already be canonical, so it cannot
    # reintroduce drift (e.g. question:q01-... or question:5-...).
    if not _NUMERIC_LOCAL_PART_RE.fullmatch(local_part):
        raise EntityCommandError(f"Non-canonical numeric id {entity_id!r}; expected <kind>:NNNN-slug (4-digit number)")
    return entity_id


def _next_numeric_local_part(project_root: Path, kind: str, slug: str) -> str:
    root = project_root / resolve_path_policy(kind).root
    max_n = 0
    if root.is_dir():
        for path in root.glob("*.md"):
            match = _NUMERIC_SCAN_RE.match(path.stem)
            if match is not None:
                max_n = max(max_n, int(match.group(1)))
    return f"{max_n + 1:0{LOCAL_PART_WIDTH}d}-{slug}"


def _numeric_slug_fragment(slug: str) -> str:
    if _NUMERIC_LOCAL_PART_RE.fullmatch(slug):
        return slug.split("-", 1)[1]
    return slug


def generate_entity_id(
    project_root: Path,
    kind: str,
    title: str,
    entity_id: str | None,
    slug: str | None,
    today: date | None = None,
) -> str:
    del today  # dates live in frontmatter, not the id
    if entity_id is not None:
        return validate_entity_id(kind, entity_id)

    strategy = resolve_path_policy(kind).strategy
    if strategy == "citekey":
        raise EntityCommandError(f"{kind} requires an explicit --id (citekey), e.g. {kind}:Adams2025")
    if strategy == "singleton":
        raise EntityCommandError(f"{kind} is a singleton; it is not created via this path")
    if strategy == "verbatim":
        raise EntityCommandError(f"{kind} requires an explicit --id; sequence identities are not derived from a title")

    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)
    if strategy in ("slug", "id-local"):
        return f"{kind}:{slug_value}"
    slug_value = _numeric_slug_fragment(slug_value)
    return f"{kind}:{_next_numeric_local_part(project_root, kind, slug_value)}"


def path_for_entity(kind: str, entity_id: str, today: date) -> Path:
    del today
    validate_entity_id(kind, entity_id)
    local_part = entity_id.split(":", 1)[1]
    return resolve_path_policy(kind).root / f"{local_part}.md"


def _entity_not_found_error(project_root: Path, ref: str) -> EntityCommandError:
    roots = ", ".join(str(policy.root) for policy in entity_policies(project_root).values())
    return EntityCommandError(f"Entity not found: {ref}. Searched source roots: {roots}")


def resolve_entity_ref(project_root: Path, ref: str) -> str:
    entities = _load_markdown_entities(project_root)
    if ":" in ref:
        for entity in entities:
            if entity["id"] == ref:
                return ref
        raise _entity_not_found_error(project_root, ref)

    matches = [entity["id"] for entity in entities if _entity_ref_matches(entity["id"], ref)]
    if not matches:
        raise _entity_not_found_error(project_root, ref)
    if len(matches) > 1:
        raise EntityCommandError(f"Ambiguous entity reference {ref}: {', '.join(sorted(matches))}")
    return matches[0]


def _numeric_variants(token: str) -> set[str]:
    """Return {token, zero-padded-to-width(token)} when token starts with digits."""
    match = re.match(r"^(\d+)(.*)$", token)
    if match is None:
        return {token}
    digits, rest = match.group(1), match.group(2)
    return {token, f"{int(digits):0{LOCAL_PART_WIDTH}d}{rest}"}


def _entity_ref_matches(entity_id: str, ref: str) -> bool:
    kind, local_part = entity_id.split(":", 1)
    for variant in _numeric_variants(ref):
        if local_part == variant or local_part.startswith(f"{variant}-"):
            return True

    shortform = _SHORTFORM_REF_RE.fullmatch(ref)
    if shortform is None:
        return False
    if _SHORTFORM_ENTITY_KINDS.get(shortform.group("prefix").lower()) != kind:
        return False

    unprefixed_ref = shortform.group("number") + shortform.group("suffix")
    for variant in _numeric_variants(unprefixed_ref):
        if local_part == variant or local_part.startswith(f"{variant}-"):
            return True
    return False


def find_entity(project_root: Path, ref: str) -> EntityLocation:
    project_root = project_root.resolve()
    entity_id = resolve_entity_ref(project_root, ref)
    for entity in _load_markdown_entities(project_root):
        if entity["id"] != entity_id:
            continue
        path = entity["path"]
        # Body WITHOUT the `.lstrip("\n")` `_parse_markdown_file` applies. Every writer that consumes
        # an `EntityLocation` (`_prepare_write`, `append_entity_note`, `entity_review`, `consolidate`)
        # renders it straight back as `"---\n" + frontmatter + "---\n" + body`, so a stripped leading
        # newline is not a parse detail -- it deletes the blank line after the closing fence on every
        # edit, in a diff the author never asked for.
        #
        # `read_text` (universal newlines), NOT the `newline=""` reader: line endings stay normalized
        # to LF the way they always were. Preserving CRLF here would only half-preserve it, since
        # `_render_markdown` emits LF fences and a freshly-dumped LF frontmatter block regardless --
        # the file would come back with mixed endings, which is worse than either whole answer.
        frontmatter, body = split_frontmatter(path.read_text(encoding="utf-8"))
        kind = str(frontmatter.get("kind") or entity_id.split(":", 1)[0])
        return EntityLocation(
            entity_id=entity_id,
            kind=kind,
            title=str(frontmatter.get("title") or ""),
            status=str(frontmatter.get("status") or ""),
            path=path,
            rel_path=path.relative_to(project_root).as_posix(),
            frontmatter=dict(frontmatter),
            body=body,
        )
    raise _entity_not_found_error(project_root, ref)


def build_entity_markdown(
    *,
    kind: str,
    entity_id: str,
    title: str,
    status: str,
    related: list[str],
    source_refs: list[str],
    today: date,
    with_sections: list[str] | None = None,
    without_sections: list[str] | None = None,
    no_hints: bool = False,
    extra_frontmatter: Mapping[str, object] | None = None,
) -> str:
    from science_model.templates import MIGRATED_KINDS, EntityTemplateError, Renderer

    _validate_extra_frontmatter(extra_frontmatter)
    if kind in MIGRATED_KINDS:
        validated_id = validate_entity_id(kind, entity_id)
        local_part = validated_id.split(":", 1)[1]
        date_prefix = f"{today.isoformat()}-"
        slug_value = local_part.removeprefix(date_prefix) if local_part.startswith(date_prefix) else local_part
        fields: dict[str, object] = {
            "entity_id": validated_id,
            "kind": kind,
            "title": title,
            "status": status,
            "related": related,
            "source_refs": source_refs,
            "created": today.isoformat(),
            "updated": today.isoformat(),
            "slug": slug_value,
            "local_part": local_part,
            "nn": _leading_number(local_part),
        }
        try:
            text = Renderer(today=today).render(
                kind,
                fields=fields,
                with_keys=list(with_sections or []),
                without_keys=list(without_sections or []),
                no_hints=no_hints,
            )
        except EntityTemplateError as exc:
            raise EntityCommandError(str(exc)) from exc
        if extra_frontmatter:
            return _merge_extra_frontmatter(text, extra_frontmatter)
        return text

    frontmatter: dict[str, object] = {
        "id": validate_entity_id(kind, entity_id),
        "kind": kind,
        "title": title,
        "status": status,
        "related": related,
        "source_refs": source_refs,
        "created": today.isoformat(),
        "updated": today.isoformat(),
    }
    if extra_frontmatter:
        frontmatter.update(extra_frontmatter)
    body = _entity_body_template(kind, title)
    return "---\n" + _dump_frontmatter(frontmatter) + "---\n" + body


def _merge_extra_frontmatter(text: str, extra_frontmatter: Mapping[str, object]) -> str:
    if not text.startswith("---\n"):
        raise EntityCommandError("Rendered entity template has no frontmatter block")
    rest = text[len("---\n") :]
    frontmatter_text, separator, body = rest.partition("---\n")
    if not separator:
        raise EntityCommandError("Rendered entity template has no closing frontmatter fence")
    frontmatter = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(frontmatter, dict):
        raise EntityCommandError("Rendered entity template frontmatter is not a mapping")
    frontmatter.update(extra_frontmatter)
    return "---\n" + _dump_frontmatter(frontmatter) + "---\n" + body


def _validate_extra_frontmatter(extra_frontmatter: Mapping[str, object] | None) -> None:
    if not extra_frontmatter:
        return
    reserved = sorted(set(extra_frontmatter) & _EXTRA_FRONTMATTER_RESERVED_KEYS)
    if reserved:
        raise EntityCommandError(f"extra frontmatter cannot override core field(s): {', '.join(reserved)}")


def _entity_body_template(kind: str, title: str) -> str:
    if kind == "evidence-line":
        return f"# {title}\n\n## Evidence\n\n\n## Interpretation\n\n\n## Notes\n"
    return f"# {title}\n\n## Summary\n\n\n## Notes\n"


def _leading_number(local_part: str) -> str:
    match = _ID_PREFIX_RE.match(local_part)
    return match.group("number") if match else ""


def parse_origin_spec(spec: str) -> dict[str, object]:
    """Parse a compact ``[+]TYPE[:REF][@DATE]`` origin spec into a validated dict.

    A single leading ``+`` marks the origin ``independent`` (converged
    independently of the entity's other origins). The remainder is parsed as
    before: a trailing ``@DATE`` is split off first, then ``TYPE:REF`` splits on
    the first ``:`` (so ``literature:paper:smith2019`` yields ref
    ``paper:smith2019``). A bare literature ref (no ``paper:``/``cite:`` prefix)
    is normalized to ``cite:<ref>``. Raises via ``OriginRecord.model_validate``
    if the resulting record is invalid (e.g. a literature origin with no ref, or
    a non ``YYYY-MM-DD`` date).
    """
    independent = False
    if spec.startswith("+"):
        independent = True
        spec = spec[1:]
    date: str | None = None
    if "@" in spec:
        spec, date = spec.rsplit("@", 1)
    if ":" in spec:
        type_, ref = spec.split(":", 1)
    else:
        type_, ref = spec, None
    if type_ == "literature" and ref and not ref.startswith(("paper:", "cite:")):
        ref = f"cite:{ref}"
    record: dict[str, object] = {"type": type_}
    if ref:
        record["ref"] = ref
    if date:
        record["date"] = date
    if independent:
        record["independent"] = True
    OriginRecord.model_validate(record)  # validate/normalize; raises on bad input
    return record


def create_entity(
    project_root: Path,
    kind: str,
    title: str,
    *,
    entity_id: str | None = None,
    slug: str | None = None,
    explicit_path: Path | None = None,
    status: str | None = None,
    related: list[str] | None = None,
    source_refs: list[str] | None = None,
    today: date | None = None,
    with_sections: list[str] | None = None,
    without_sections: list[str] | None = None,
    no_hints: bool = False,
    extra_frontmatter: Mapping[str, object] | None = None,
) -> EntityWriteResult:
    project_root = project_root.resolve()
    today_value = today or date.today()
    resolve_path_policy(kind)
    if slug is not None and entity_id is not None:
        raise EntityCommandError("Use either --slug or --id, not both")

    entity_id_value = generate_entity_id(project_root, kind, title, entity_id, slug, today=today_value)
    status_value = status or _DEFAULT_STATUS[kind]
    _validate_status(project_root, kind, status_value)
    rel_path = _resolve_destination_rel_path(project_root, kind, entity_id_value, explicit_path, today_value)
    destination = project_root / rel_path
    if destination.exists():
        raise EntityCommandError(f"Destination already exists: {rel_path}")

    text = build_entity_markdown(
        kind=kind,
        entity_id=entity_id_value,
        title=title,
        status=status_value,
        related=list(related or []),
        source_refs=list(source_refs or []),
        today=today_value,
        with_sections=with_sections,
        without_sections=without_sections,
        no_hints=no_hints,
        extra_frontmatter=extra_frontmatter,
    )
    warnings, _ = _validate_prospective_write(
        project_root=project_root,
        rel_path=rel_path,
        text=text,
        target_entity_id=entity_id_value,
    )
    # Pre-write guard only — generate_entity_id above owns the actual derivation.
    # Calling the same function batch planners call is what makes their up-front
    # check binding: anything they accept, this accepts.
    if entity_id is None:
        resolve_entity_slug(title, slug)

    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, destination)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return EntityWriteResult(entity_id=entity_id_value, path=destination, warnings=warnings)


def _reject_if_archived(project_root: Path, ref: str) -> None:
    """Archived members are frozen: tool-mediated content edits must go through
    ``entities unarchive`` -> edit -> re-archive, so the index ``digest_insight``
    cannot silently drift from the relocated file. The live scan already skips
    ``_archive/`` (so an archived ref otherwise surfaces only as a bare
    ``Entity not found``); this converts that incidental block into an explicit,
    actionable error. Raw filesystem edits under ``_archive/`` remain out of scope,
    like raw grep — the contract is the tool surface."""
    from science_tool.archive import load_archive_index

    index = load_archive_index(project_root)
    canonical = index.resolvable_ids().get(ref)
    if canonical is None:
        return
    row = index.active_by_id[canonical]
    if row.consolidated_into:
        why = f"consolidated into {row.consolidated_into}"
    elif row.superseded_by:
        why = f"superseded by {row.superseded_by}"
    else:
        why = "archived"
    raise EntityCommandError(
        f"{ref} is archived ({why}); archived entities are frozen. "
        f"Run `science entities unarchive {canonical}`, edit, then re-archive."
    )


# ---------------------------------------------------------------------------------------------
# THE WRITE BOUNDARY — ONE mechanism, in two halves, and BOTH halves are PRIVATE.
#
# `_prepare_write` merges, renders, and validates; it writes NOTHING. The split is what makes
# `mark_superseded`'s all-or-none claim true rather than aspirational: a caller can learn that a
# write WOULD be rejected before a byte hits the disk.
#
# THE COMMIT HALF IS PRIVATE TOO, AND SO IS THE VALUE IT TAKES. A public `commit_entity_write` that
# writes whatever `.text` it is handed -- by contract, WITHOUT validating it -- is not a hole in the
# boundary; it IS a second, unvalidated writer, and a plain frozen dataclass is one call away:
#
#     _commit_write(_PreparedWrite(entity_id=..., path=..., text="<anything>", warnings=()))
#
# SO THE TOKEN CARRIES A SEAL, AND THE SEAL IS BOUND TO THE PAYLOAD rather than merely possessed. A
# bare sentinel -- "hold this object and you are trusted" -- is a BEARER token, and a bearer token
# can be carried onto content it never vouched for, with no private import at all:
#
#     dataclasses.replace(legitimately_prepared, text="<anything>")   # copies the sentinel
#
# `replace()` re-runs `__post_init__`, so an identity check on a sentinel sees the SAME trusted
# object and waves through text that was never validated. The seal must therefore be a statement
# ABOUT THE PAYLOAD: an HMAC over every field the write consists of. `replace()` recomputes nothing,
# so it carries the OLD seal onto NEW bytes and `__post_init__` refuses it.
#
# THE HONEST CLAIM, since Python has no private constructors: this does not make forgery
# *impossible* -- `_SEAL_KEY` is reachable by anyone willing to import a private name and recompute
# the digest. It makes forgery **inexpressible by accident**: not by a plausible refactor, not by a
# helpful `replace()`, not by a caller who thought this was the supported path.
# ---------------------------------------------------------------------------------------------

_SEAL_KEY = secrets.token_bytes(32)  # module-private, per-process; never exported, never persisted


def _seal(entity_id: str, path: Path, text: str) -> str:
    """An HMAC over EVERY field the write actually consists of.

    Covering `text` alone would leave `replace(prepared, path=<elsewhere>)` free to redirect
    validated bytes at an unvalidated file.
    """
    payload = "\0".join((entity_id, str(path), text)).encode("utf-8")
    return hmac.new(_SEAL_KEY, payload, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class _PreparedWrite:
    entity_id: str
    path: Path
    text: str  # fully rendered, fully validated -- nothing left to decide
    warnings: tuple[str, ...]
    seal: str  # HMAC of (entity_id, path, text). No default, deliberately.

    def __post_init__(self) -> None:
        # `compare_digest`, not `==`: this is a MAC check, and constant-time comparison is what a MAC
        # check is. Runs on `replace()` too, which is the entire point.
        if not hmac.compare_digest(self.seal, _seal(self.entity_id, self.path, self.text)):
            raise TypeError(
                "_PreparedWrite is not constructible, and its seal does not travel: it is the "
                "proof that _prepare_write validated THIS text for THIS path. Call _prepare_write."
            )


def _prepare_write_with_date(
    project_root: Path,
    ref: str,
    fields: Mapping[str, object],
    *,
    updated_default: str,
    appends: Mapping[str, list[str]] | None = None,
) -> _PreparedWrite:
    """PRIVATE. Merge, render, validate, SEAL. Writes NOTHING.

    Takes a `fields` MAPPING and has NO `**kwargs`, so the one place a derived field can be set is a
    call site -- and there are exactly two in the codebase: `edit_entity` (which cannot express
    `superseded_by`) and `consolidation._prepare_supersession` (which derives it from an admitted
    canonical edge).

    `appends` carries `edit_entity`'s unique-append list semantics, which need the record's CURRENT
    value. Doing it here rather than in the caller keeps the boundary to ONE `find_entity` and one
    archive check -- and keeps their ORDER, so an archived ref still reports the actionable
    `_reject_if_archived` error instead of a bare "Entity not found".

    THE LIFECYCLE GATE LIVES HERE, in the half that writes nothing, and that is what makes it a gate
    rather than a lament: a terminal transition with no basis, or with a successor that names
    nothing, fails BEFORE a byte reaches the disk instead of landing and surfacing as a `validate`
    WARN afterwards. Both entry points inherit it because both come through here. A boundary that
    governed only the path nobody was going to corrupt would be decoration.

    `updated_default` is INJECTED rather than read from the clock, so a preview and a later apply
    of the same plan produce byte-identical output. `_prepare_write` is the legacy entry point that
    injects today's date; `consolidation._prepare_supersession` injects the plan's preview date.
    """
    project_root = project_root.resolve()
    _reject_if_archived(project_root, ref)
    location = find_entity(project_root, ref)

    frontmatter = dict(location.frontmatter)
    for key, additions in (appends or {}).items():
        frontmatter[key] = _append_unique_string_values(frontmatter.get(key), additions)
    for key, value in fields.items():
        if key == "status":
            _validate_status(project_root, location.kind, str(value))
        frontmatter[key] = value
    frontmatter.setdefault("updated", updated_default)

    # Cheapest authority first: the composed schema decides SHAPE, and it decides it about one
    # record, so it needs no corpus at all. On an UNPINNED project it still refuses the schema-2
    # vocabulary -- a gate that reads "not migrated" as "no rules" is not a gate.
    _schema_gate_or_raise(project_root, location.kind, fields, frontmatter)

    text = _render_markdown(frontmatter, location.body)
    warnings, prospective = _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(location.rel_path),
        text=text,
        target_entity_id=location.entity_id,
    )
    # ...then the ONE question the schema structurally cannot answer, against the corpus as it WOULD
    # be. Resolving a successor against the BASELINE would ask about a corpus this write is changing.
    _resolution_check_or_raise(location.kind, frontmatter, prospective)

    return _PreparedWrite(
        entity_id=location.entity_id,
        path=location.path,
        text=text,
        warnings=tuple(warnings),
        seal=_seal(location.entity_id, location.path, text),
    )


def _prepare_write(
    project_root: Path,
    ref: str,
    fields: Mapping[str, object],
    *,
    appends: Mapping[str, list[str]] | None = None,
) -> _PreparedWrite:
    """Legacy entry point: inject today's date as the `updated` default. See
    `_prepare_write_with_date` for the full contract; this is a thin delegator preserved for its
    existing call sites (`edit_entity`)."""
    return _prepare_write_with_date(
        project_root, ref, fields, updated_default=date.today().isoformat(), appends=appends
    )


# Fields an UNMIGRATED hypothesis project may not have written to it. Each would put a schema-2
# meaning onto a schema-1 record -- the two-vocabularies-at-once state this whole arc exists to
# abolish, and which the write surface was handing out:
#
#   verdict, closure_basis -- MEAN NOTHING before the fold. Under schema 1 the verdict IS `status`,
#     and there is no lifecycle for a closure to discharge, so `verdict: supported` beside
#     `status: proposed` and `phase: active` is three fields with no agreement between them.
#   status -- the kind descriptor now offers ONLY the new lifecycle words (`active`, `complete`,
#     `retired`, ...). Any value `_validate_status` accepts is therefore a new-vocabulary word landing
#     on an old-vocabulary record; an OLD word (`proposed`) it already refuses. So there is no coherent
#     status edit to an unmigrated hypothesis -- both answers are wrong, and the field is refused.
#   resynthesized_into -- a schema-2 lineage field. Written unpinned it evades the reverse implication
#     (a successor names what a record has INSTEAD of a future, so `active` + a successor is a
#     contradiction) -- which the schema enforces only once the project has pinned.
#
# The lineage guard for an unmigrated corpus does not live here: a HAND-AUTHORED dangling successor is
# still caught by `check_dangling_lineage` on the validate path, over every entity regardless of pin.
# This gate governs only what the WRITE boundary may MANUFACTURE.
_PIN_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"status", "verdict", "closure_basis", "resynthesized_into"}
)


def _schema_gate_or_raise(
    project_root: Path, kind: str, fields: Mapping[str, object], frontmatter: Mapping[str, object]
) -> None:
    """D3.1 at the WRITE boundary: the composed JSON Schema is the authority on a record's shape.

    The KIND gate first -- `PROJECT_MIXIN_NAMES` is the migration slice list, and a kind with no
    project mixin has no schema to be held to. Then the project's PIN decides which of two things
    happens, and NEITHER of them is "nothing":

    * PINNED -> validate the merged record against the composed schema. A terminal transition with
      no basis fails here, before a byte is written.
    * UNPINNED -> the schema cannot be applied (it would reject `--title` over a `phase:` key the
      migration is coming for) -- but the schema-2 VOCABULARY must still be refused. Skipping this is
      what let `--verdict supported`, `--status complete`, and `--resynthesized-into` land on an
      unmigrated file. An unpinned project is not one the rules do not reach; it is one that has not
      earned the new words yet. `--title` and other schema-1 fields still go through.
    """
    if kind not in PROJECT_MIXIN_NAMES:
        return

    try:
        schema = load_project_schema_if_pinned(project_root)
    except (ValidationError, ValueError) as exc:
        # A near-miss pin OR an illegal pin value lands HERE now (the shared authority raises a plain
        # ValueError; a pydantic model elsewhere in the config raises ValidationError). Either must
        # arrive as a CLI error, not a traceback -- an author who typed `entity_schema_verison` or
        # `"2"` needs the sentence, not a stack.
        raise EntityCommandError(f"science.yaml is not valid, so this write cannot be checked:\n{exc}") from exc
    if schema is None:
        offered = sorted(_PIN_REQUIRED_FIELDS & {k for k, v in fields.items() if v is not None})
        if offered:
            raise EntityCommandError(
                f"{', '.join(offered)} cannot be written here: this project has not declared "
                f"`entity_schema_version: 2`, so its {kind} records still carry the verdict in "
                f"`status` and speak the pre-fold vocabulary. Writing {offered[0]!r} now would leave "
                f"the record speaking two vocabularies at once. Migrate the project first: "
                f"`science entity migrate-hypothesis --apply`."
            )
        return

    try:
        schema.validator.validate_as(dict(frontmatter), schema.profile_for(kind))
    except EntityValidationError as exc:
        raise EntityCommandError(
            f"{frontmatter.get('id', kind)}: the edit does not satisfy the {kind} schema\n  {exc}"
        ) from exc


def _resolution_check_or_raise(
    kind: str, frontmatter: Mapping[str, object], sources: ProjectSources
) -> None:
    """The D3 escape hatch, ENUMERATED: does this record's lineage name a real, live, OTHER entity?

    ☠️ ASKED OF EVERY RECORD THAT NAMES A SUCCESSOR, whatever its status. It used to run only on
    `superseded` records, and a status is a bad proxy for "has lineage" in both directions: an
    `active` hypothesis carrying `resynthesized_into: [hypothesis:9999-nope]` was never checked at
    all, while a `superseded` one discharged by `closure_basis` -- no successor, nothing to resolve --
    built a resolver anyway, so an alias collision between two OTHER entities blocked its `--title`
    edit. `has_lineage_to_resolve` now asks about lineage.

    NOT gated on the pin, unlike the schema check, and the asymmetry is the point. `superseded_by`
    meant `superseded_by` in the OLD vocabulary too, so a dangling successor is authorable in an
    unmigrated project today -- which is precisely the corpus that most needs the guard. Gating this
    on the pin would arm it only for the projects that had already been made safe.

    Gated on the kind, though, because `check_resolution` asks whether a successor is a live
    HYPOTHESIS. Pointing it at another kind would measure that kind against a set it is not in.
    """
    if kind not in PROJECT_MIXIN_NAMES:
        return
    record = dict(frontmatter)
    if not has_lineage_to_resolve(record):
        return  # no resolver built: see `has_lineage_to_resolve` for why that matters

    try:
        resolver = ReferenceResolver.from_entities(
            sources.entities,
            manual_aliases=sources.manual_aliases,
            archive_alias_tokens=sources.archive_alias_tokens,
            identity_table=build_identity_table(sources),
        )
    except AliasCollisionError as exc:
        raise EntityCommandError(
            f"cannot check this entity's lineage: the corpus has a duplicated alias ({exc}). "
            "Resolve the collision, then retry -- a successor cannot be verified against a corpus "
            "that disagrees about which entity an id names."
        ) from exc

    live = {e.canonical_id for e in sources.entities if e.kind == kind}
    violations = check_resolution(record, targets=resolver, live_hypotheses=live)
    if violations:
        raise EntityCommandError("; ".join(v.message for v in violations))


def _commit_write(prepared: _PreparedWrite) -> EntityWriteResult:
    """PRIVATE. Authenticate the prepared value, then atomically replace the file.

    It performs no schema or resolution decisions; it re-verifies the proof that those decisions
    covered THESE bytes for THIS path. Construction-time verification is NOT the write boundary:
    Python erases the annotation at runtime, so this can otherwise be handed a duck-typed object
    that never ran `__post_init__` -- and a legitimately prepared frozen instance can still be
    changed with `object.__setattr__` after its constructor check ran.
    """
    if not isinstance(prepared, _PreparedWrite):
        raise TypeError("a prepared write must be earned from _prepare_write")
    if not hmac.compare_digest(
        prepared.seal, _seal(prepared.entity_id, prepared.path, prepared.text)
    ):
        raise TypeError("prepared-write seal does not cover the bytes and path being committed")
    _atomic_replace_text(prepared.path, prepared.text)
    return EntityWriteResult(
        entity_id=prepared.entity_id, path=prepared.path, warnings=list(prepared.warnings)
    )


# THE AUTHORED SURFACE. Explicit, keyword-only, and it must NEVER grow a `**kwargs`.
#
# It does NOT gain a `superseded_by` parameter. `superseded_by` is DERIVED, and putting it on the
# authored-edit surface would recreate the second authored spelling design rev 10 exists to delete:
# an author could write a resolvable `superseded_by` with NO canonical edge behind it, the schema
# would pass, `check_resolution` would pass, and the entity would be superseded according to
# nothing. A `**kwargs` here would smuggle it back in -- and would make a named-parameter guard
# anti-informative, because the absence of the name is exactly what a VAR_KEYWORD signature
# guarantees whether or not the field is reachable.
def edit_entity(
    project_root: Path,
    ref: str,
    *,
    title: str | None = None,
    status: str | None = None,
    verdict: str | None = None,
    closure_basis: str | None = None,
    resynthesized_into: list[str] | None = None,  # AUTHORED: no canonical relation behind it
    related: list[str] | None = None,
    source_refs: list[str] | None = None,
    updated: date | None = None,
    today: date | None = None,
) -> EntityWriteResult:
    """The AUTHORED-edit surface. Prepare, then commit.

    ONE generic lifecycle boundary, not four invented verbs. `--closure-basis` and `--verdict` are
    accepted ATOMICALLY with the transition they discharge, which is what lets a single schema check
    inside `_prepare_write` decide the whole thing: `status: retired` with no basis is not a write
    that needs a follow-up, it is a write that never happens.
    """
    fields: dict[str, object] = {}
    if title is not None:
        fields["title"] = title
    if status is not None:
        fields["status"] = status
    if verdict is not None:
        fields["verdict"] = verdict
    if closure_basis is not None:
        fields["closure_basis"] = closure_basis
    if resynthesized_into is not None:
        fields["resynthesized_into"] = resynthesized_into
    fields["updated"] = (updated or today or date.today()).isoformat()

    appends: dict[str, list[str]] = {}
    if related:
        appends["related"] = related
    if source_refs:
        appends["source_refs"] = source_refs

    return _commit_write(_prepare_write(project_root, ref, fields, appends=appends))


def append_entity_note(
    project_root: Path,
    ref: str,
    note: str,
    note_date: date | None = None,
) -> EntityWriteResult:
    note_text = note.strip()
    if not note_text:
        raise EntityCommandError("Note cannot be empty")
    project_root = project_root.resolve()
    _reject_if_archived(project_root, ref)
    location = find_entity(project_root, ref)
    frontmatter = dict(location.frontmatter)
    date_value = note_date or date.today()
    frontmatter["updated"] = date_value.isoformat()
    body = append_note_to_body(location.body, f"- {date_value.isoformat()}: {note_text}")
    text = _render_markdown(frontmatter, body)
    warnings, _ = _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(location.rel_path),
        text=text,
        target_entity_id=location.entity_id,
    )
    _atomic_replace_text(location.path, text)
    return EntityWriteResult(entity_id=location.entity_id, path=location.path, warnings=warnings)


_REMOVABLE_FRONTMATTER_REF_KEYS: frozenset[str] = frozenset(
    {
        "related",
        "source_refs",
        "supersedes",
        "superseded_by",
        "resynthesized_into",
        "consolidates",
        "consolidated_into",
        "members",
        "member_refs",
        "depends_on",
        "blockers",
    }
)

def plan_entity_removal(project_root: Path, target: str) -> EntityRemovalPlan:
    project_root = project_root.resolve()
    location = _resolve_removal_location(project_root, target)
    terms = _removal_search_terms(location)
    safe_hits: list[EntityReferenceHit] = []
    manual_hits: list[EntityReferenceHit] = []
    for path in iter_project_files(project_root):
        if path == location.path:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not any(term in text for term in terms):
            continue
        frontmatter, body = _parse_markdown_file(path) if path.suffix == ".md" else ({}, text)
        rel_path = path.relative_to(project_root).as_posix()
        removable = _removable_frontmatter_refs(frontmatter, terms)
        safe_hits.extend(
            EntityReferenceHit(
                path=path,
                rel_path=rel_path,
                line=_line_for_frontmatter_key(text, key),
                kind="safe structured reference",
                detail=f"{key}: {value}",
            )
            for key, value in removable
        )
        if path.suffix == ".md" and frontmatter:
            manual_hits.extend(_manual_frontmatter_reference_hits(path, rel_path, text, frontmatter, terms))
        manual_text = body if path.suffix == ".md" and frontmatter else text
        manual_hits.extend(_manual_reference_hits(path, rel_path, manual_text, terms))
    return EntityRemovalPlan(
        entity_id=location.entity_id,
        path=location.path,
        rel_path=location.rel_path,
        safe_hits=safe_hits,
        manual_hits=manual_hits,
    )


def remove_entity(project_root: Path, target: str) -> EntityRemovalPlan:
    project_root = project_root.resolve()
    plan = plan_entity_removal(project_root, target)
    for hit in sorted(plan.safe_hits, key=lambda item: (item.rel_path, item.line, item.detail)):
        _remove_frontmatter_ref(hit.path, set(_removal_search_terms_from_plan(plan)))
    plan.path.unlink()
    return plan


def _resolve_removal_location(project_root: Path, target: str) -> EntityLocation:
    candidate = Path(target).expanduser()
    if candidate.suffix == ".md" or "/" in target:
        resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
        if not resolved.is_relative_to(project_root):
            raise EntityCommandError("entity path must be inside the project root")
        if not resolved.is_file():
            raise EntityCommandError(f"Entity file not found: {target}")
        frontmatter, body = _parse_markdown_file(resolved)
        entity_id = frontmatter.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise EntityCommandError(f"Entity file has no frontmatter id: {target}")
        kind = str(frontmatter.get("kind") or entity_id.split(":", 1)[0])
        return EntityLocation(
            entity_id=entity_id,
            kind=kind,
            title=str(frontmatter.get("title") or ""),
            status=str(frontmatter.get("status") or ""),
            path=resolved,
            rel_path=resolved.relative_to(project_root).as_posix(),
            frontmatter=dict(frontmatter),
            body=body,
        )
    return find_entity(project_root, target)


def _removal_search_terms(location: EntityLocation) -> tuple[str, ...]:
    local_part = location.entity_id.split(":", 1)[1] if ":" in location.entity_id else location.path.stem
    terms = {
        location.entity_id,
        local_part,
        location.rel_path,
        Path(location.rel_path).stem,
    }
    return tuple(sorted(term for term in terms if term))


def _removal_search_terms_from_plan(plan: EntityRemovalPlan) -> tuple[str, ...]:
    local_part = plan.entity_id.split(":", 1)[1] if ":" in plan.entity_id else Path(plan.rel_path).stem
    terms = {plan.entity_id, local_part, plan.rel_path, Path(plan.rel_path).stem}
    return tuple(sorted(term for term in terms if term))


def _removable_frontmatter_refs(frontmatter: dict[str, Any], terms: tuple[str, ...]) -> list[tuple[str, str]]:
    removable: list[tuple[str, str]] = []
    term_set = set(terms)
    for key in _REMOVABLE_FRONTMATTER_REF_KEYS:
        value = frontmatter.get(key)
        if isinstance(value, list):
            removable.extend((key, item) for item in value if isinstance(item, str) and item in term_set)
        elif isinstance(value, str) and value in term_set:
            removable.append((key, value))
    return removable


def _line_for_frontmatter_key(text: str, key: str) -> int:
    for index, line in enumerate(text.splitlines(), start=1):
        if line.startswith(f"{key}:"):
            return index
    return 1


def _manual_reference_hits(path: Path, rel_path: str, text: str, terms: tuple[str, ...]) -> list[EntityReferenceHit]:
    hits: list[EntityReferenceHit] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        matched = next((term for term in terms if term in line), None)
        if matched is None:
            continue
        hits.append(
            EntityReferenceHit(
                path=path,
                rel_path=rel_path,
                line=line_number,
                kind="manual reference",
                detail=matched,
            )
        )
    return hits


def _manual_frontmatter_reference_hits(
    path: Path,
    rel_path: str,
    text: str,
    frontmatter: dict[str, Any],
    terms: tuple[str, ...],
) -> list[EntityReferenceHit]:
    hits: list[EntityReferenceHit] = []
    term_set = set(terms)
    for key, value in frontmatter.items():
        if key in _REMOVABLE_FRONTMATTER_REF_KEYS:
            continue
        if not _frontmatter_value_contains_term(value, term_set):
            continue
        hits.append(
            EntityReferenceHit(
                path=path,
                rel_path=rel_path,
                line=_line_for_frontmatter_key(text, str(key)),
                kind="manual reference",
                detail=str(key),
            )
        )
    return hits


def _frontmatter_value_contains_term(value: object, terms: set[str]) -> bool:
    if isinstance(value, str):
        return value in terms
    if isinstance(value, list):
        return any(_frontmatter_value_contains_term(item, terms) for item in value)
    if isinstance(value, dict):
        return any(_frontmatter_value_contains_term(item, terms) for item in value.values())
    return False


def _remove_frontmatter_ref(path: Path, terms: set[str]) -> None:
    frontmatter, body = _parse_markdown_file(path)
    changed = False
    for key in _REMOVABLE_FRONTMATTER_REF_KEYS:
        value = frontmatter.get(key)
        if isinstance(value, list):
            retained = [item for item in value if not (isinstance(item, str) and item in terms)]
            if retained != value:
                changed = True
                if retained:
                    frontmatter[key] = retained
                else:
                    frontmatter.pop(key, None)
        elif isinstance(value, str) and value in terms:
            changed = True
            frontmatter.pop(key, None)
    if changed:
        _atomic_replace_text(path, _render_markdown(frontmatter, body))


def list_entities(
    project_root: Path,
    kind: str | None = None,
    status: str | None = None,
    related: str | None = None,
    *,
    include_hidden: bool = False,
    include_archived: bool = False,
) -> list[dict[str, object]]:
    if related is not None and include_archived:
        # The archive index carries no relation data, so the `related` filter cannot
        # be evaluated against archived rows. Fail loud rather than silently include
        # unfiltered archived rows or silently drop them.
        raise EntityCommandError(
            "--related cannot be combined with --include-archived (the archive index does not carry relation data)"
        )
    sources = load_project_sources(project_root.resolve())
    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
    )
    related_key = _resolved_ref_key(resolver, related) if related is not None else None

    rows: list[dict[str, object]] = []
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
    return sorted(rows, key=lambda row: str(row["id"]))


def _resolved_ref_key(resolver: ReferenceResolver, raw: str) -> str:
    resolution = resolver.resolve(raw, allow_cross_kind_fallback=True, allow_tag=True)
    return resolution.canonical_id or raw


def _related_refs_match(related_refs: list[str], related_key: str, resolver: ReferenceResolver) -> bool:
    for raw in related_refs:
        if raw == related_key:
            return True
        resolution = resolver.resolve(raw, allow_cross_kind_fallback=True, allow_tag=True)
        if resolution.canonical_id == related_key:
            return True
    return False


def load_local_entity_index(project_root: Path) -> dict[str, ProjectEntity]:
    """Return local project entities keyed by canonical id.

    Domain/catalog entities are intentionally excluded: task blockers are
    project-state dependencies such as tasks, datasets, workflow-runs, and
    other ProjectEntity subclasses. Cross-project entities are out of scope.
    """
    index: dict[str, ProjectEntity] = {}
    for entity in load_project_sources(project_root.resolve()).entities:
        if isinstance(entity, ProjectEntity):
            index[entity.canonical_id] = entity
    return index


def load_local_entity_ids(project_root: Path) -> set[str]:
    """Return canonical ids for local ProjectEntity records."""
    return set(load_local_entity_index(project_root))


def graph_is_stale(project_root: Path, graph_path: Path) -> bool:
    if not graph_path.exists():
        return True
    markdown_paths = [path for root in MarkdownAdapter().scan_roots for path in project_root.glob(f"{root}/**/*.md")]
    source_paths = [*markdown_paths, *project_root.glob("tasks/**/*.md")]
    if not source_paths:
        return False
    newest_source_mtime = max(path.stat().st_mtime for path in source_paths)
    return newest_source_mtime > graph_path.stat().st_mtime


def append_note_to_body(body: str, note_line: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if not _NOTES_HEADING_RE.fullmatch(line):
            continue
        insert_at = len(lines)
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("## ") and not _NOTES_HEADING_RE.fullmatch(lines[next_index]):
                insert_at = next_index
                break
        before = lines[:insert_at]
        after = lines[insert_at:]
        while before and before[-1] == "":
            before.pop()
        updated_lines = [*before, "", note_line]
        if after:
            updated_lines.extend(["", *after])
        return "\n".join(updated_lines)

    return body.rstrip("\n") + "\n\n## Notes\n\n" + note_line


def _dump_frontmatter(frontmatter: dict[str, object]) -> str:
    """Serialize entity frontmatter without mangling the fields it is not editing.

    Every authored write in this module is a READ-MODIFY-WRITE: the whole frontmatter mapping is
    parsed, one or two keys are changed, and the mapping is dumped back. So any lossy dumper option
    is not a formatting preference -- it rewrites fields the caller never touched.

    `allow_unicode=False` escaped every non-ASCII character, and the default `width=80` then folded
    the over-long escaped scalar across lines. A `science entity edit --status` on a title containing
    an em-dash produced `title: "t166 \\u2014 Stage-transition edges \\u2014 Implementation\\  \\ Plan"`
    -- unreadable, and a diff on a line the edit had nothing to do with. Over a bulk lifecycle sweep
    that is one line of intended change per file buried in a file of title churn.
    """
    return yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )


def _render_markdown(frontmatter: dict[str, object], body: str) -> str:
    return "---\n" + _dump_frontmatter(frontmatter) + "---\n" + body


def _append_unique_string_values(existing: object, additions: list[str]) -> list[str]:
    values = [str(value) for value in existing] if isinstance(existing, list) else []
    for addition in additions:
        if addition not in values:
            values.append(addition)
    return values


def _atomic_replace_text(path: Path, text: str) -> None:
    atomic_write_text(path, text)


def _validate_status(project_root: Path, kind: str, status: str) -> None:
    """Reject a status the kind does not declare — and know about PROJECT-LOCAL kinds.

    It used to index `_STATUS_VALUES[kind]`, which holds BUILT-IN kinds only, so editing an entity of
    a kind the project declares in its own manifest raised a bare `KeyError` out of a CLI command.
    `valid_statuses` is the one function that reads local manifests, and it answers `None` for a
    local kind that declares NO vocabulary — an OPEN set, not an empty one. Reading `None` as "no
    status is valid" would refuse every edit to those kinds instead of accepting any.
    """
    try:
        allowed = valid_statuses(kind, project_root=project_root)
    except KeyError:
        raise EntityCommandError(f"Unknown entity kind: {kind}") from None
    if allowed is not None and status not in allowed:
        raise EntityCommandError(
            f"Invalid status for {kind}: {status} (expected one of {', '.join(sorted(allowed))})"
        )


def _resolve_destination_rel_path(
    project_root: Path,
    kind: str,
    entity_id: str,
    explicit_path: Path | None,
    today: date,
) -> Path:
    if explicit_path is None:
        return path_for_entity(kind, entity_id, today)
    if explicit_path.is_absolute():
        raise EntityCommandError("--path must be relative to the project root")
    if ".." in explicit_path.parts:
        raise EntityCommandError("--path must not contain '..'")
    if explicit_path.suffix != ".md":
        raise EntityCommandError("--path must point to a .md file")
    resolved = (project_root / explicit_path).resolve()
    if not resolved.is_relative_to(project_root):
        raise EntityCommandError("--path must stay within the project root")
    if not any(explicit_path == root or explicit_path.is_relative_to(root) for root in _ALLOWED_EXPLICIT_ROOTS):
        raise EntityCommandError("--path must be under entities/")
    return explicit_path


def _validate_prospective_writes(
    *,
    project_root: Path,
    markdown_overrides: Mapping[str, str],
    allowed_unresolved_sources: Collection[str],
    include_commons: bool = True,
) -> tuple[list[str], ProjectSources]:
    """Audit warnings, AND the corpus as it would be after these writes — the ONE core.

    `markdown_overrides` maps rel path -> content (`""` models a REMOVED file). Forward
    `related`/`source_refs` unresolved references whose source is in `allowed_unresolved_sources`
    are downgraded to warnings (they resolve via the alias net); any other new blocking audit
    failure raises `EntityCommandError`. Returns the prospective sources it already built.
    """
    def _audit_rows(project_sources: ProjectSources) -> list[AuditRow]:
        verdict = audit_project_sources(project_sources)
        if verdict.status == "unwired":
            raise EntityCommandError(f"source audit could not run ({verdict.code}): {verdict.reason}")
        return verdict.rows

    baseline_rows = _audit_rows(load_project_sources(project_root, include_commons=include_commons))
    prospective = load_project_sources(
        project_root, markdown_overrides=dict(markdown_overrides), include_commons=include_commons
    )
    prospective_rows = _audit_rows(prospective)

    baseline_keys = {_audit_row_key(row) for row in baseline_rows}
    new_rows = [row for row in prospective_rows if _audit_row_key(row) not in baseline_keys]
    warnings = [_format_preexisting_warning(row) for row in baseline_rows if row.get("status") == "fail"]
    blocking_rows: list[Mapping[str, object]] = []
    for row in new_rows:
        if _is_allowed_unresolved_target_warning(row, allowed_unresolved_sources):
            warnings.append(_format_new_warning(row))
            continue
        if row.get("status") == "fail":
            blocking_rows.append(row)
    if blocking_rows:
        raise EntityCommandError("; ".join(_format_blocking_row(row) for row in blocking_rows))
    return warnings, prospective


def _validate_prospective_write(
    *,
    project_root: Path,
    rel_path: Path,
    text: str,
    target_entity_id: str,
    include_commons: bool = True,
) -> tuple[list[str], ProjectSources]:
    """Single-document prospective validation — delegates to the batch core."""
    return _validate_prospective_writes(
        project_root=project_root,
        markdown_overrides={rel_path.as_posix(): text},
        allowed_unresolved_sources={target_entity_id},
        include_commons=include_commons,
    )


def _audit_row_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("check", "")),
        str(row.get("status", "")),
        str(row.get("source", "")),
        str(row.get("field", "")),
        str(row.get("target", "")),
        str(row.get("details", "")),
    )


def _is_allowed_unresolved_target_warning(row: Mapping[str, object], allowed_sources: Collection[str]) -> bool:
    return (
        row.get("check") == "unresolved_reference"
        and row.get("status") == "fail"
        and row.get("source") in allowed_sources
        and row.get("field") in {"related", "source_refs"}
    )


def _format_ref_location(row: Mapping[str, object]) -> str:
    """`field -> target` locator, when both are present, so the author can see
    exactly which reference failed without a separate validate pass."""
    field = str(row.get("field", "")).strip()
    target = str(row.get("target", "")).strip()
    if field and target:
        return f" ({field} -> {target})"
    if target:
        return f" ({target})"
    return ""


def _format_preexisting_warning(row: Mapping[str, object]) -> str:
    return (
        f"pre-existing audit failure: {row.get('check')} on {row.get('source')}"
        f"{_format_ref_location(row)}: {row.get('details')}"
    )


def _format_new_warning(row: Mapping[str, object]) -> str:
    return f"{row.get('check')} on {row.get('source')}{_format_ref_location(row)}: {row.get('details')}"


def _format_blocking_row(row: Mapping[str, object]) -> str:
    return f"{row.get('check')} on {row.get('source')}{_format_ref_location(row)}: {row.get('details')}"


def load_markdown_entities(project_root: Path, kind: str | None = None) -> list[dict[str, Any]]:
    """Public policy-root loader for markdown entities."""
    return _load_markdown_entities(project_root, kind=kind)


def parse_markdown_entity_file(path: Path) -> tuple[dict[str, Any], str]:
    """Public markdown frontmatter/body parser for entity files."""
    return _parse_markdown_file(path)


def parse_markdown_entity_file_preserving_body(path: Path) -> tuple[dict[str, Any], str]:
    """Public markdown frontmatter/body parser that preserves body bytes exactly."""
    return _parse_markdown_file_preserving_body(path)


def numeric_variants(token: str) -> set[str]:
    """Public id variant helper for local numeric entity references."""
    return _numeric_variants(token)


def shortform_for_kind(kind: str) -> str | None:
    """Return the registered shortform prefix for an entity kind, if any."""
    for shortform, entity_kind in _SHORTFORM_ENTITY_KINDS.items():
        if entity_kind == kind:
            return shortform
    return None


def _load_markdown_entities(project_root: Path, kind: str | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    try:
        policies = entity_policies(project_root)
    except (yaml.YAMLError, ValidationError, ValueError, OSError) as exc:
        raise EntityCommandError(f"Entity policy configuration is not valid:\n{exc}") from exc
    for policy_kind, policy in policies.items():
        if kind is not None and policy_kind != kind:
            continue
        root = project_root / policy.root
        if not root.is_dir():
            continue
        for path in iter_entity_markdown(root):
            frontmatter, _ = _parse_markdown_file(path)
            entity_id = frontmatter.get("id")
            entity_kind = frontmatter.get("kind")
            if isinstance(entity_id, str) and isinstance(entity_kind, str):
                entities.append({"id": entity_id, "kind": entity_kind, "path": path, "frontmatter": frontmatter})
    return entities


def _parse_markdown_file(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ({}, text)
    try:
        _, frontmatter_text, body = text.split("---\n", 2)
    except ValueError:
        return ({}, text)
    frontmatter = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(frontmatter, dict):
        return ({}, body)
    return (frontmatter, body.lstrip("\n"))


def _parse_markdown_file_preserving_body(path: Path) -> tuple[dict[str, Any], str]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    return split_frontmatter(text)

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml
from science_model.entities import OriginRecord, ProjectEntity
from science_model.profiles import EntityKind, ProfileManifest, load_profile_manifest
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import EntityFilenameStrategy

from science_tool.entity_scan import iter_entity_markdown
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import (
    load_project_sources,
    local_profile_sources_dir,
    resolve_local_profile_name,
)
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter

LOCAL_PART_WIDTH = 4


class EntityCommandError(ValueError):
    """Raised for user-correctable entity CLI errors."""


@dataclass(frozen=True)
class EntityPathPolicy:
    root: Path
    strategy: EntityFilenameStrategy


_KIND_DESCRIPTORS = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)

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
    result = (policies, kind_warnings)
    _LOCAL_POLICY_CACHE[cache_key] = result
    return result


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
_STATUS_VALUES: dict[str, frozenset[str]] = {ek.name: frozenset(ek.statuses) for ek in _KIND_DESCRIPTORS if ek.statuses}
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
        "proposed",
        "under-investigation",
        "partially-supported",
        "supported",
        "weakened",
        "refuted",
        "complete",
        "contested",
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


def write_entity_file(
    entity: Any,  # any typed entity exposing .kind, .id, and Pydantic .model_dump()
    *,
    project_root: Path,
    body: str,
    as_of: date | None = None,
) -> None:
    """Write a typed entity to its canonical ``entities/<kind>/<slug>.md`` file.

    Single canonical entity writer (also used by ``dag.workbench``). Path from
    ``resolve_path_policy``; frontmatter from the typed model's ``model_dump``; the
    Markdown ``body`` is supplied by the caller. ``created`` is preserved on upsert;
    ``updated`` advances to ``as_of`` (or today).
    """
    today = as_of or date.today()
    kind = entity.kind
    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    policy = resolve_path_policy(kind, project_root=project_root)
    dest = project_root / policy.root / f"{local_part}.md"

    existing_created: str | None = None
    if dest.exists():
        try:
            existing_fm, _ = _parse_markdown_file(dest)
            existing_created = existing_fm.get("created")
            if existing_created is not None:
                existing_created = str(existing_created)
        except (yaml.YAMLError, ValueError, OSError):
            existing_created = None

    text = render_entity_text(
        entity,
        body=body,
        created=existing_created if existing_created is not None else today.isoformat(),
        updated=today.isoformat(),
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)


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


def resolve_entity_ref(project_root: Path, ref: str) -> str:
    entities = _load_markdown_entities(project_root)
    if ":" in ref:
        for entity in entities:
            if entity["id"] == ref:
                return ref
        raise EntityCommandError(f"Entity not found: {ref}")

    matches = [entity["id"] for entity in entities if _entity_ref_matches(entity["id"], ref)]
    if not matches:
        raise EntityCommandError(f"Entity not found: {ref}")
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
        frontmatter, body = _parse_markdown_file(path)
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
    roots = ", ".join(str(policy.root) for policy in _BUILTIN_MARKDOWN_POLICIES.values())
    raise EntityCommandError(f"Entity not found: {ref}. Searched source roots: {roots}")


def build_entity_markdown(
    *,
    kind: str,
    entity_id: str,
    title: str,
    status: str,
    related: list[str],
    source_refs: list[str],
    today: date,
    phase: str | None = None,
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
            "phase": phase or "active",
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
    phase: str | None = None,
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
    _validate_status(kind, status_value)
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
        phase=phase,
        with_sections=with_sections,
        without_sections=without_sections,
        no_hints=no_hints,
        extra_frontmatter=extra_frontmatter,
    )
    warnings = _validate_prospective_write(
        project_root=project_root,
        rel_path=rel_path,
        text=text,
        target_entity_id=entity_id_value,
    )
    if slug is None and entity_id is None:
        full_slug = normalize_to_slug(title)
        used_slug = truncate_slug_on_word_boundary(full_slug, DERIVED_SLUG_MAX_LENGTH)
        if used_slug != full_slug:
            warnings.insert(
                0,
                f"Title truncated to derive id slug '{used_slug}' "
                f"(dropped '{full_slug[len(used_slug) :].lstrip('-')}'). "
                f"The id is {entity_id_value}; pass --slug to choose a different one.",
            )

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


def edit_entity(
    project_root: Path,
    ref: str,
    *,
    title: str | None = None,
    status: str | None = None,
    related: list[str] | None = None,
    source_refs: list[str] | None = None,
    updated: date | None = None,
    today: date | None = None,
) -> EntityWriteResult:
    project_root = project_root.resolve()
    _reject_if_archived(project_root, ref)
    location = find_entity(project_root, ref)
    frontmatter = dict(location.frontmatter)
    if title is not None:
        frontmatter["title"] = title
    if status is not None:
        _validate_status(location.kind, status)
        frontmatter["status"] = status
    if related:
        frontmatter["related"] = _append_unique_string_values(frontmatter.get("related"), related)
    if source_refs:
        frontmatter["source_refs"] = _append_unique_string_values(frontmatter.get("source_refs"), source_refs)
    frontmatter["updated"] = (updated or today or date.today()).isoformat()

    text = _render_markdown(frontmatter, location.body)
    warnings = _validate_prospective_write(
        project_root=project_root,
        rel_path=Path(location.rel_path),
        text=text,
        target_entity_id=location.entity_id,
    )
    _atomic_replace_text(location.path, text)
    return EntityWriteResult(entity_id=location.entity_id, path=location.path, warnings=warnings)


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
    warnings = _validate_prospective_write(
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

_REFERENCE_SCAN_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        ".worktrees",
        "__pycache__",
        "node_modules",
    }
)


def plan_entity_removal(project_root: Path, target: str) -> EntityRemovalPlan:
    project_root = project_root.resolve()
    location = _resolve_removal_location(project_root, target)
    terms = _removal_search_terms(location)
    safe_hits: list[EntityReferenceHit] = []
    manual_hits: list[EntityReferenceHit] = []
    for path in _iter_reference_scan_files(project_root):
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


def _iter_reference_scan_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _REFERENCE_SCAN_SKIP_DIRS for part in path.relative_to(project_root).parts):
            continue
        files.append(path)
    return files


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
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
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
    return yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False)


def _render_markdown(frontmatter: dict[str, object], body: str) -> str:
    return "---\n" + _dump_frontmatter(frontmatter) + "---\n" + body


def _append_unique_string_values(existing: object, additions: list[str]) -> list[str]:
    values = [str(value) for value in existing] if isinstance(existing, list) else []
    for addition in additions:
        if addition not in values:
            values.append(addition)
    return values


def _atomic_replace_text(path: Path, text: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _validate_status(kind: str, status: str) -> None:
    if status not in _STATUS_VALUES[kind]:
        raise EntityCommandError(f"Invalid status for {kind}: {status}")


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


def _validate_prospective_write(
    *,
    project_root: Path,
    rel_path: Path,
    text: str,
    target_entity_id: str,
    include_commons: bool = True,
) -> list[str]:
    rel_path_text = rel_path.as_posix()
    baseline_rows, _ = audit_project_sources(load_project_sources(project_root, include_commons=include_commons))
    prospective_rows, _ = audit_project_sources(
        load_project_sources(project_root, markdown_overrides={rel_path_text: text}, include_commons=include_commons)
    )

    baseline_keys = {_audit_row_key(row) for row in baseline_rows}
    new_rows = [row for row in prospective_rows if _audit_row_key(row) not in baseline_keys]
    warnings = [_format_preexisting_warning(row) for row in baseline_rows if row.get("status") == "fail"]
    blocking_rows: list[Mapping[str, object]] = []
    for row in new_rows:
        if _is_allowed_unresolved_target_warning(row, target_entity_id):
            warnings.append(_format_new_warning(row))
            continue
        if row.get("status") == "fail":
            blocking_rows.append(row)
    if blocking_rows:
        raise EntityCommandError("; ".join(_format_blocking_row(row) for row in blocking_rows))
    return warnings


def _audit_row_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("check", "")),
        str(row.get("status", "")),
        str(row.get("source", "")),
        str(row.get("field", "")),
        str(row.get("target", "")),
        str(row.get("details", "")),
    )


def _is_allowed_unresolved_target_warning(row: Mapping[str, object], target_entity_id: str) -> bool:
    return (
        row.get("check") == "unresolved_reference"
        and row.get("status") == "fail"
        and row.get("source") == target_entity_id
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
    for policy_kind, policy in _BUILTIN_MARKDOWN_POLICIES.items():
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
    if text.startswith("---\r\n"):
        newline = "\r\n"
    elif text.startswith("---\n"):
        newline = "\n"
    else:
        return ({}, text)
    after_opening_marker = text[len("---" + newline) :]
    closing_marker = f"{newline}---{newline}"
    closing_marker_index = after_opening_marker.find(closing_marker)
    if closing_marker_index == -1:
        return ({}, text)
    frontmatter_text = after_opening_marker[:closing_marker_index]
    body = after_opening_marker[closing_marker_index + len(closing_marker) :]
    frontmatter = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(frontmatter, dict):
        return ({}, body)
    return (frontmatter, body)

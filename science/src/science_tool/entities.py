from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import yaml

from science_model.entities import ProjectEntity
from science_model.profiles.schema import EntityFilenameStrategy
from science_model.profiles import EntityKind, ProfileManifest, load_profile_manifest
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
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
    ek.name: EntityPathPolicy(Path(ek.home), ek.strategy)
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
_VALID_STRATEGIES: frozenset[str] = frozenset({"numeric", "citekey", "slug"})

# Set of directory (or file) names that belong to core kinds' homes.  A local
# kind whose resolved home has the same final path component would silently
# overwrite the core entry in the dir→kind inference map built by the migrator
# (_project_dir_to_kind in entity_layout_migration.py).  Computed once at
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
_DEFAULT_STATUS: dict[str, str] = {
    ek.name: ek.default_status for ek in _KIND_DESCRIPTORS if ek.default_status
}
_STATUS_VALUES: dict[str, frozenset[str]] = {
    ek.name: frozenset(ek.statuses) for ek in _KIND_DESCRIPTORS if ek.statuses
}
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
    if strategy == "slug":
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

    frontmatter = entity.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
    frontmatter["id"] = entity.id
    frontmatter["kind"] = kind
    frontmatter.setdefault("status", default_status(kind))
    for derived in ("canonical_id", "content_preview", "content", "file_path"):
        frontmatter.pop(derived, None)
    frontmatter["created"] = existing_created if existing_created is not None else today.isoformat()
    frontmatter["updated"] = today.isoformat()

    text = _render_markdown(frontmatter, body)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_replace_text(dest, text)


def append_entity_source_ref(file_path: Path, ref: str, *, as_of: date | None = None) -> bool:
    """Append ``ref`` to an existing entity file's ``source_refs`` frontmatter, preserving
    the body. Returns True if added, False if already present. Used by promotion LINK so a
    hand-authored proposition's prose is never clobbered. When a ref is added, `updated`
    advances to ``as_of`` (or today), matching other entity mutations."""
    frontmatter, body = _parse_markdown_file(file_path)
    refs = list(frontmatter.get("source_refs") or [])
    if ref in refs:
        return False
    refs.append(ref)
    frontmatter["source_refs"] = refs
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    _atomic_replace_text(file_path, _render_markdown(frontmatter, body))
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
    if not entity_id.startswith(prefix):
        raise EntityCommandError(f"Entity id must use prefix {prefix}")
    local_part = entity_id[len(prefix) :]
    strategy = resolve_path_policy(kind).strategy
    if strategy == "singleton":
        raise EntityCommandError(f"{kind} is a singleton and has no per-instance id")
    if strategy == "citekey":
        if not _CITEKEY_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid citekey local part: {entity_id}")
        return entity_id
    if strategy == "slug":
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
    if strategy == "slug":
        return f"{kind}:{slug_value}"
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
        kind = str(frontmatter.get("type") or frontmatter.get("kind") or entity_id.split(":", 1)[0])
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
) -> str:
    from science_model.templates import MIGRATED_KINDS, EntityTemplateError, Renderer

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
            return Renderer(today=today).render(
                kind,
                fields=fields,
                with_keys=list(with_sections or []),
                without_keys=list(without_sections or []),
                no_hints=no_hints,
            )
        except EntityTemplateError as exc:
            raise EntityCommandError(str(exc)) from exc

    frontmatter: dict[str, object] = {
        "id": validate_entity_id(kind, entity_id),
        "type": kind,
        "title": title,
        "status": status,
        "related": related,
        "source_refs": source_refs,
        "created": today.isoformat(),
        "updated": today.isoformat(),
    }
    body = _entity_body_template(kind, title)
    return "---\n" + _dump_frontmatter(frontmatter) + "---\n" + body


def _entity_body_template(kind: str, title: str) -> str:
    del kind
    return f"# {title}\n\n## Summary\n\n\n## Notes\n"


def _leading_number(local_part: str) -> str:
    match = _ID_PREFIX_RE.match(local_part)
    return match.group("number") if match else ""


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
) -> EntityWriteResult:
    project_root = project_root.resolve()
    today_value = today or date.today()
    if kind == "concept":
        raise EntityCommandError("Source-authored concepts are not supported; use graph add concept instead")
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


def list_entities(
    project_root: Path,
    kind: str | None = None,
    status: str | None = None,
    related: str | None = None,
    *,
    include_hidden: bool = False,
) -> list[dict[str, str]]:
    sources = load_project_sources(project_root.resolve())
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    related_key = _resolved_ref_key(resolver, related) if related is not None else None

    rows: list[dict[str, str]] = []
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
            }
        )
    return sorted(rows, key=lambda row: row["id"])


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
) -> list[str]:
    rel_path_text = rel_path.as_posix()
    baseline_rows, _ = audit_project_sources(load_project_sources(project_root))
    prospective_rows, _ = audit_project_sources(
        load_project_sources(project_root, markdown_overrides={rel_path_text: text})
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


def _load_markdown_entities(project_root: Path, kind: str | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for policy_kind, policy in _BUILTIN_MARKDOWN_POLICIES.items():
        if kind is not None and policy_kind != kind:
            continue
        root = project_root / policy.root
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            frontmatter, _ = _parse_markdown_file(path)
            entity_id = frontmatter.get("id")
            entity_kind = frontmatter.get("type") or frontmatter.get("kind")
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

"""`science entity migrate-specs` (S3b) — canonicalize legacy/loose spec docs to numeric entities.

Ships the migration; does NOT flip `spec:` resolution (`_ANNOTATION_REF_PREFIXES` is untouched).
ONE planning authority (`_plan_all`) produces both the flip-readiness report AND the frozen
transaction, so a dry run exercises every refusal a `--apply` would. The design is
`docs/plans/2026-07-18-specs-plans-as-entities-s3b-design.md`.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from science_model.frontmatter import render_frontmatter, split_frontmatter

from science_tool.entities import (
    _REFERENCE_SCAN_SKIP_DIRS,
    _REMOVABLE_FRONTMATTER_REF_KEYS,
    derive_slug,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
)
from science_tool.entity_reservation import propose_number
from science_tool.markdown_scan import iter_prose_matches
from science_tool.reference_rewrite import (
    _LINK_RE,
    RewriteReport,
    _relative_link,
    _resolve_link,
    _split_target,
    _sub_prose_matches,
    plan_reference_rewrite,
    rewrite_outbound_links,
)
from science_tool.text_scan import (
    MAX_SCANNABLE_BYTES,
    TEXT_SUFFIXES,
    _CODE_SUFFIXES,
    iter_scannable_files,
    read_text_or_skip,
)

JOURNAL_PATH: Path = Path(".science/spec-migration.journal")

# The load-derived keys, enumerated EXACTLY. `canonical_id` OVERRIDES the id-derived value at load,
# so an authored one would disagree with the freshly minted numeric id.
RUNTIME_ONLY: frozenset[str] = frozenset(
    {"project", "file_path", "content", "content_preview", "canonical_id"}
)

LEGACY_ALIAS: frozenset[str] = frozenset({"type", "date", "related_questions", "related_specs"})

CANONICAL_SPEC_STATUS: frozenset[str] = frozenset(
    {"draft", "active", "complete", "superseded", "retired", "archived"}
)

# Unambiguous legacy -> canonical only. Anything else refuses (the operator pre-edits the status).
_STATUS_MAP: dict[str, str] = {
    "draft": "draft",
    "proposed": "draft",
    "design": "draft",
    "active": "active",
    "in-progress": "active",
    "current": "active",
    "complete": "complete",
    "completed": "complete",
    "implemented": "complete",
}


class SpecMigrationRefused(RuntimeError):
    """The migration will not proceed. NOTHING has been written."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _dedup(items: list[Any]) -> list[Any]:
    """Order-preserving dedup (first occurrence wins)."""
    seen: set[Any] = set()
    out: list[Any] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def project_legacy_frontmatter(frontmatter: Mapping[str, Any], *, source_rel: str) -> tuple[str, dict]:
    """Project ONE legacy spec doc's frontmatter to the canonical spec schema.

    Returns ``(old_id, projected_frontmatter)``; keeps ``id: <old_id>`` and ``kind: spec``. The old id
    is appended to ``aliases`` only by the coordinator's mint step. Refuses, naming the file, on any
    ambiguity — it never invents a value.
    """
    fm = dict(frontmatter)

    present_runtime = sorted(RUNTIME_ONLY & set(fm))
    if present_runtime:
        raise SpecMigrationRefused(
            f"{source_rel}: authors load-derived key(s) {present_runtime!r}, which are not "
            "authorable frontmatter (they are derived at load)."
        )

    declared_kind = fm.get("kind")
    declared_type = fm.get("type")
    if declared_kind is not None and declared_type is not None and declared_kind != declared_type:
        raise SpecMigrationRefused(f"{source_rel}: kind {declared_kind!r} and type {declared_type!r} disagree.")
    kind = declared_kind if declared_kind is not None else declared_type
    if kind != "spec":
        raise SpecMigrationRefused(f"{source_rel}: not a spec (kind/type {kind!r}).")
    fm["kind"] = "spec"
    fm.pop("type", None)

    old_id = fm.get("id")
    if not isinstance(old_id, str) or not old_id.startswith("spec:"):
        raise SpecMigrationRefused(
            f"{source_rel}: a spec doc without a declared `spec:` id; identity is authoritative "
            "and never guessed from a filename."
        )
    title = fm.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SpecMigrationRefused(f"{source_rel}: missing `title:`.")

    date = fm.pop("date", None)
    for field in ("created", "updated"):
        if fm.get(field):
            continue
        if date:
            fm[field] = date
        else:
            raise SpecMigrationRefused(f"{source_rel}: `{field}` is absent and there is no `date:` to seed it.")

    status = fm.get("status")
    if status is not None:
        if status in CANONICAL_SPEC_STATUS:
            pass
        elif status in _STATUS_MAP:
            fm["status"] = _STATUS_MAP[status]
        else:
            raise SpecMigrationRefused(
                f"{source_rel}: status {status!r} maps to no canonical spec status. "
                "Pre-edit the doc's status; the migration will not guess."
            )

    related = _dedup(
        [
            *_as_list(fm.get("related")),
            *_as_list(fm.pop("related_questions", None)),
            *_as_list(fm.pop("related_specs", None)),
        ]
    )
    if related:
        fm["related"] = related

    return old_id, fm


# A well-formed spec id: `spec:` + a local part with no path separators or traversal.
_SPEC_ID_RE = re.compile(r"^spec:[A-Za-z0-9][A-Za-z0-9._-]*$")
_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})
# A leading ISO date (`YYYY-MM-DD-…`) is the dominant legacy id convention. Its 4-digit head is a
# CALENDAR YEAR, not a canonical spec sequence number, so such a doc must be MINTED a fresh
# `spec:NNNN-slug`, never mistaken for an already-numeric relocation. See `_numeric_of`.
_ISO_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}(-|$)")


@dataclass(frozen=True)
class LegacySpec:
    source_rel: str
    old_id: str
    frontmatter: dict
    body: str
    already_numeric: int | None  # the NNNN if the id is a full conforming numeric local part, else None


@dataclass(frozen=True)
class Singleton:
    rel_path: str
    old_id: str


@dataclass(frozen=True)
class ScanSkip:
    path: str
    reason: str


@dataclass(frozen=True)
class Discovery:
    legacy: list[LegacySpec]
    singletons: list[Singleton]
    scan_skips: list[ScanSkip]


def _spec_root(project_root: Path) -> str:
    return str(resolve_path_policy("spec", project_root=project_root).root)


def _singleton_homes(project_root: Path) -> set[str]:
    homes: set[str] = set()
    for kind in markdown_entity_kinds(project_root):
        policy = resolve_path_policy(kind, project_root=project_root)
        if policy.strategy == "singleton":
            homes.add(str(policy.root))
    return homes


def _numeric_of(old_id: str) -> int | None:
    """The NNNN of a FULL conforming `spec:NNNN-slug` sequence id, else None.

    A prefix-only match (e.g. `spec:0007-x/../../outside`) is rejected — `local_part_conforms`
    requires the whole numeric shape. An ISO-date-prefixed id (`spec:2026-03-16-…`) is also rejected:
    its 4-digit head is a calendar year, not a spec sequence number, so it is minted fresh rather than
    preserved as an already-numeric relocation."""
    local = old_id.split(":", 1)[1] if ":" in old_id else old_id
    if _ISO_DATE_PREFIX.match(local):
        return None
    if local_part_conforms("spec", local):
        return int(local[:4])
    return None


def discover_specs(project_root: Path) -> Discovery:
    """Discover legacy spec docs, singleton-home spec files, and scan skips over a COMPLETE walk.

    The walk covers every `TEXT_SUFFIXES` file (not just Markdown), so an oversized non-Markdown file
    is caught as a `scan_skip` rather than silently dropped by the 5 MiB cap. Only Markdown files are
    parsed for spec candidacy; non-Markdown readability is covered by classification (Task 5).
    """
    project_root = Path(project_root).resolve()
    spec_root = _spec_root(project_root)
    singleton_homes = _singleton_homes(project_root)

    legacy: list[LegacySpec] = []
    singletons: list[Singleton] = []
    scan_skips: list[ScanSkip] = []

    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_root).as_posix()
        if any(part in _REFERENCE_SCAN_SKIP_DIRS for part in path.relative_to(project_root).parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            oversized = path.stat().st_size > MAX_SCANNABLE_BYTES
        except OSError as exc:
            scan_skips.append(ScanSkip(path=rel, reason=str(exc)))
            continue
        if oversized:
            scan_skips.append(ScanSkip(path=rel, reason="exceeds MAX_SCANNABLE_BYTES"))
            continue
        if path.suffix.lower() not in _MARKDOWN_SUFFIXES:
            continue  # non-markdown: readability is covered by classification
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            scan_skips.append(ScanSkip(path=rel, reason=str(exc)))
            continue

        frontmatter, body = split_frontmatter(text)
        if not frontmatter:
            continue
        if frontmatter.get("type") != "spec" and frontmatter.get("kind") != "spec":
            continue

        old_id = frontmatter.get("id")
        if rel in singleton_homes:
            singletons.append(Singleton(rel_path=rel, old_id=old_id if isinstance(old_id, str) else ""))
            continue

        stem_conforms = path.stem and local_part_conforms("spec", path.stem, project_root=project_root)
        if rel.startswith(f"{spec_root}/") and stem_conforms:
            if old_id == f"spec:{path.stem}":
                continue  # a clean conforming entity
            raise SpecMigrationRefused(
                f"{rel}: in-home spec filename stem {path.stem!r} and declared id {old_id!r} disagree."
            )

        if not isinstance(old_id, str) or not old_id.startswith("spec:"):
            raise SpecMigrationRefused(
                f"{rel}: a spec doc without a declared `spec:` id; identity is authoritative "
                "and never guessed from a filename."
            )
        if _SPEC_ID_RE.match(old_id) is None:
            raise SpecMigrationRefused(f"{rel}: malformed spec id {old_id!r} (path separators are not allowed).")

        legacy.append(
            LegacySpec(source_rel=rel, old_id=old_id, frontmatter=frontmatter, body=body, already_numeric=_numeric_of(old_id))
        )

    return Discovery(legacy=legacy, singletons=singletons, scan_skips=scan_skips)


_NUMERIC_LOCAL_RE = re.compile(r"^(\d{4})-")


@dataclass(frozen=True)
class Allocation:
    id_substitutions: dict[str, str]
    dest_rel: dict[str, str]
    new_local_part: dict[str, str]
    aliased: frozenset[str]
    preserved_ids: frozenset[str]


def _number_taken_at_home(project_root: Path, number: int) -> bool:
    """True iff `number` is backed by a committed spec .md OR an archived spec id."""
    from science_tool.archive import load_archive_index

    directory = Path(project_root) / _spec_root(Path(project_root))
    if directory.is_dir():
        for entry in directory.glob("*.md"):
            match = _NUMERIC_LOCAL_RE.match(entry.stem)
            if match is not None and int(match.group(1)) == number:
                return True
    for entity_id in load_archive_index(Path(project_root)).resolvable_ids():
        prefix, _, local = entity_id.partition(":")
        if prefix != "spec":
            continue
        match = _NUMERIC_LOCAL_RE.match(local)
        if match is not None and int(match.group(1)) == number:
            return True
    return False


def allocate_ids(project_root: Path, legacy: list[LegacySpec]) -> Allocation:
    """Assign a deterministic `spec:NNNN-slug` to each legacy doc (see design Component 4)."""
    project_root = Path(project_root).resolve()
    spec_root = _spec_root(project_root)
    start = propose_number(project_root, "spec")

    id_subs: dict[str, str] = {}
    dest_rel: dict[str, str] = {}
    new_local: dict[str, str] = {}
    aliased: set[str] = set()
    preserved: set[str] = set()
    forbidden: set[int] = set()

    for spec in legacy:  # preserved relocations first: keep the id, spend its number
        if spec.already_numeric is None:
            continue
        if _number_taken_at_home(project_root, spec.already_numeric):
            raise SpecMigrationRefused(
                f"{spec.source_rel}: already-numeric spec {spec.old_id} keeps number "
                f"{spec.already_numeric:04d}, which is taken at {spec_root}/. Resolve the clash."
            )
        local = spec.old_id.split(":", 1)[1]
        new_local[spec.old_id] = local
        dest_rel[spec.old_id] = f"{spec_root}/{local}.md"
        preserved.add(spec.old_id)
        forbidden.add(spec.already_numeric)

    number = start
    for spec in sorted((s for s in legacy if s.already_numeric is None), key=lambda s: s.old_id):
        while number in forbidden:
            number += 1
        local = f"{number:04d}-{derive_slug(spec.frontmatter['title'])}"
        id_subs[spec.old_id] = f"spec:{local}"
        new_local[spec.old_id] = local
        dest_rel[spec.old_id] = f"{spec_root}/{local}.md"
        aliased.add(spec.old_id)
        forbidden.add(number)
        number += 1

    return Allocation(
        id_substitutions=id_subs,
        dest_rel=dest_rel,
        new_local_part=new_local,
        aliased=frozenset(aliased),
        preserved_ids=frozenset(preserved),
    )


_SPEC_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_-])spec:[A-Za-z0-9._/-]+")
_TRAILING_PUNCT = ".,;:)"
_READ_INVISIBLE_FIELDS = ("same_as", "blocked_by", "evidence_refs", "participants", "propositions", "source", "commits_to")


@dataclass(frozen=True)
class RefRecord:
    ref: str
    surface: str
    target: str  # "migrated" | "canonical" | "unresolved"
    group: str
    in_file: str


def _live_spec_ids(project_root: Path) -> set[str]:
    """Ids + aliases of the specs already living under entities/specs/ (already-canonical targets)."""
    ids: set[str] = set()
    directory = Path(project_root) / _spec_root(Path(project_root))
    if not directory.is_dir():
        return ids
    for path in directory.glob("*.md"):
        try:
            frontmatter, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if isinstance(frontmatter.get("id"), str):
            ids.add(frontmatter["id"])
        for alias in frontmatter.get("aliases") or []:
            if isinstance(alias, str):
                ids.add(alias)
    return ids


def _iter_fm_ref_values(frontmatter: dict) -> list[tuple[str, str]]:
    """(surface, token) for every structured frontmatter reference surface. Skips id/aliases."""

    def _tokens(value: Any) -> list[str]:
        return [item for item in _as_list(value) if isinstance(item, str)]

    out: list[tuple[str, str]] = []
    for key in _REMOVABLE_FRONTMATTER_REF_KEYS:
        out.extend((key, token) for token in _tokens(frontmatter.get(key)))
    for relation in frontmatter.get("relations") or []:
        if isinstance(relation, dict) and isinstance(relation.get("target"), str):
            out.append(("relations[].target", relation["target"]))
    out.extend(("discusses", token) for token in _tokens(frontmatter.get("discusses")))
    if "spec" in frontmatter:
        out.extend(("spec-key", token) for token in _tokens(frontmatter.get("spec")))
    for key in _READ_INVISIBLE_FIELDS:
        out.extend((key, token) for token in _tokens(frontmatter.get(key)))
    return out


def _group_for(surface: str, target_class: str) -> str:
    if surface == "discusses":
        return "manual_retarget"  # never a valid bundle frame, regardless of target
    if target_class == "unresolved":
        return "manual_retarget"
    if target_class == "canonical":
        return "unchanged"
    # target_class == "migrated"
    if surface in _REMOVABLE_FRONTMATTER_REF_KEYS or surface in ("relations[].target", "markdown-link"):
        return "rewritten"
    if surface in _READ_INVISIBLE_FIELDS:
        return "alias_resolved"
    return "identity_preserved"  # spec-key, prose/code mention


def classify_references(
    project_root: Path,
    *,
    id_substitutions: dict[str, str],
    live_spec_ids: set[str],
    source_rels: frozenset[str],
) -> tuple[list[RefRecord], list[ScanSkip]]:
    """Classify every inbound `spec:` reference on two axes and RETURN read skips too.

    Reuses the canonical `iter_scannable_files` so the rewrite and audit see an identical file set.
    A migrating source's own `id`/`aliases` are never scanned, so they never count as inbound refs.
    """
    project_root = Path(project_root).resolve()
    records: list[RefRecord] = []
    skips: list[ScanSkip] = []

    def target_class(token: str) -> str:
        if token in id_substitutions:
            return "migrated"
        if token in live_spec_ids:
            return "canonical"
        return "unresolved"

    for path in iter_scannable_files(project_root):
        rel = path.relative_to(project_root).as_posix()
        text, skip = read_text_or_skip(path, rel)
        if text is None:
            assert skip is not None
            skips.append(ScanSkip(path=rel, reason=skip.reason))
            continue
        is_code = path.suffix.lower() in _CODE_SUFFIXES
        is_markdown = path.suffix.lower() in _MARKDOWN_SUFFIXES
        frontmatter: dict = {}
        body = text
        if is_markdown:
            frontmatter, body = split_frontmatter(text)

        for surface, token in _iter_fm_ref_values(frontmatter):
            if not token.startswith("spec:"):
                continue
            tclass = target_class(token)
            records.append(RefRecord(ref=token, surface=surface, target=tclass, group=_group_for(surface, tclass), in_file=rel))

        if is_markdown:
            referrer_dir = PurePosixPath(rel).parent
            for match in iter_prose_matches(_LINK_RE, body):
                head, _tail = _split_target(match.group("target"))
                resolved = _resolve_link(head, referrer_dir) if head else None
                if resolved is not None and resolved in source_rels:
                    records.append(RefRecord(ref=match.group("target"), surface="markdown-link", target="migrated", group="rewritten", in_file=rel))

        scan_text = text if is_code else body
        matches = _SPEC_TOKEN_RE.finditer(scan_text) if is_code else iter_prose_matches(_SPEC_TOKEN_RE, scan_text)
        for match in matches:
            token = match.group(0).rstrip(_TRAILING_PUNCT)
            tclass = target_class(token)
            records.append(RefRecord(ref=token, surface="mention", target=tclass, group=_group_for("mention", tclass), in_file=rel))

    return records, skips


# Owner ORIGINS for non-entity claim sources: never a migrating source PATH, so a batch's own
# in-home claims can be excluded by origin without ever excluding a mapping/archive token.
_MANUAL_ALIAS_OWNER = "<mappings.yaml>"
_ARCHIVE_OWNER = "<archive>"


@dataclass(frozen=True)
class Destination:
    old_id: str
    new_id: str
    source_rel: str
    dest_rel: str
    number: int
    local_part: str
    rendered_text: str
    preimage_sha256: str


@dataclass(frozen=True)
class Transaction:
    destinations: list[Destination]
    ref_report: RewriteReport
    source_rels: frozenset[str]
    dest_rels: frozenset[str]


def _apply_path_subs_to_body(body: str, new_dir: PurePosixPath, path_subs: dict[str, str]) -> str:
    """Repoint a moved body's links whose (rebased) target is another migrating source's old path."""
    def _replace(match: re.Match[str]) -> str:
        target = match.group("target")
        head, tail = _split_target(target)
        resolved = _resolve_link(head, new_dir) if head else None
        if resolved is not None and resolved in path_subs:
            return f"[{match.group('text')}]({_relative_link(new_dir, path_subs[resolved]) + tail})"
        return match.group(0)

    return _sub_prose_matches(_LINK_RE, body, _replace)


def _render_destination(spec: LegacySpec, alloc: Allocation, id_subs: dict[str, str], path_subs: dict[str, str], new_id: str, dest_rel: str) -> str:
    """Project + assign identity + intra-batch substitute (list AND scalar) + rebase links."""
    _old_id, fm = project_legacy_frontmatter(spec.frontmatter, source_rel=spec.source_rel)

    if spec.old_id in alloc.aliased:  # minted: new id, old id appended to aliases (deduped)
        fm["id"] = new_id
        fm["aliases"] = _dedup([*_as_list(fm.get("aliases")), spec.old_id])

    for key in _REMOVABLE_FRONTMATTER_REF_KEYS:  # engine rewrites list AND scalar values; mirror that
        value = fm.get(key)
        if isinstance(value, list):
            fm[key] = [id_subs.get(item, item) if isinstance(item, str) else item for item in value]
        elif isinstance(value, str):
            fm[key] = id_subs.get(value, value)
    for relation in fm.get("relations") or []:
        if isinstance(relation, dict) and isinstance(relation.get("target"), str):
            relation["target"] = id_subs.get(relation["target"], relation["target"])

    old_dir = PurePosixPath(spec.source_rel).parent
    new_dir = PurePosixPath(dest_rel).parent
    body, _hits = rewrite_outbound_links(spec.body, old_dir, new_dir)
    body = _apply_path_subs_to_body(body, new_dir, path_subs)
    return render_frontmatter(fm, body)


def _validate_batch(project_root: Path, destinations: list[Destination]) -> None:
    """Batch-aware prospective validation — DELEGATES to the one core in `entities.py`.

    Builds the override map (EVERY destination written, EVERY source removed via `""`, so an
    intra-batch `supersedes: spec:<sibling>` resolves) and hands it to `_validate_prospective_writes`,
    allowing forward `related`/`source_refs` unresolved refs for the migrated ids (they resolve via
    the alias net post-flip). Defines no second audit-diff. `EntityCommandError` propagates to the CLI,
    which normalizes it to a refusal (Task 10)."""
    from science_tool.entities import _validate_prospective_writes

    if not destinations:
        return
    overrides: dict[str, str] = {}
    for dest in destinations:
        overrides[dest.source_rel] = ""  # post-move: the source is gone
        overrides[dest.dest_rel] = dest.rendered_text
    _validate_prospective_writes(
        project_root=project_root,
        markdown_overrides=overrides,
        allowed_unresolved_sources={dest.new_id for dest in destinations},
    )


def _all_project_claims(project_root: Path) -> dict[str, set[str]]:
    """`token -> set of owner ORIGINS`, mirroring `build_alias_map`'s claim universe.

    For every entity, its `canonical_id` and every alias are registered in BOTH exact and lowercase
    form — `build_alias_map` normalizes case, so a preflight that ignored case would let a live
    `SPEC:DATE-A` escape and then detonate as an unnormalized `AliasCollisionError` during prospective
    validation. The owner is the entity's SOURCE PATH (`entity.file_path`, project-relative posix,
    same shape as `source_rel`), so a claim is excluded by ORIGIN — an unrelated record whose id merely
    coincides with a migrating old id is NOT dropped. `manual_aliases` (the `mappings.yaml` superset;
    `archive_alias_tokens` is only its archived subset) is folded in, owned by a non-path sentinel that
    is never a migrating source."""
    from science_tool.graph.sources import load_project_sources

    claims: dict[str, set[str]] = {}

    def _add(token: object, owner: str) -> None:
        if isinstance(token, str) and token:
            claims.setdefault(token, set()).add(owner)
            claims.setdefault(token.lower(), set()).add(owner)

    sources = load_project_sources(project_root)
    for entity in sources.entities:
        _add(entity.canonical_id, entity.file_path)
        for alias in entity.aliases or []:
            _add(alias, entity.file_path)
    for token in sources.manual_aliases or {}:
        _add(token, _MANUAL_ALIAS_OWNER)
    for token in sources.archive_alias_tokens or frozenset():
        _add(token, _ARCHIVE_OWNER)
    return claims


def _collision_preflight(project_root: Path, disc: Discovery, alloc: Allocation) -> None:
    """Refuse if the batch's rendered, deduplicated claims clash with the project's global authority
    or with each other. A claim is EXISTING only when it has an owner ORIGIN outside the migrating
    source set — so a migrating spec's own claim (an in-home legacy spec loads as an entity at its
    source path) is excluded, but an unrelated record is NOT, even one whose id coincides with a
    migrating old id. Case is normalized to mirror `build_alias_map`, so a case-variant live token is
    caught here rather than at prospective validation."""
    old_ids = [spec.old_id for spec in disc.legacy]
    if len(old_ids) != len(set(old_ids)):
        raise SpecMigrationRefused("duplicate old id(s) in the discovered batch.")

    migrating_origins = {spec.source_rel for spec in disc.legacy}
    existing = {token for token, owners in _all_project_claims(project_root).items() if owners - migrating_origins}

    seen: dict[str, str] = {}

    def _check(token: str, where: str) -> None:
        if token in existing or token.lower() in existing:
            raise SpecMigrationRefused(f"{where}: {token!r} collides with an existing id/alias/mapping/archive token.")
        key = token.lower()
        if key in seen and seen[key] != where:
            raise SpecMigrationRefused(f"{where}: {token!r} collides with {seen[key]}.")
        seen[key] = where

    for spec in disc.legacy:
        new_id = alloc.id_substitutions.get(spec.old_id, spec.old_id)
        final_aliases = _dedup(
            [
                *[a for a in _as_list(spec.frontmatter.get("aliases")) if isinstance(a, str)],
                *([spec.old_id] if spec.old_id in alloc.aliased else []),
            ]
        )
        for token in _dedup([new_id, *final_aliases]):
            _check(token, spec.source_rel)


def _plan_transaction(project_root: Path, disc: Discovery, alloc: Allocation) -> Transaction:
    """Build the frozen batch plan. Writes nothing; any refusal aborts the whole batch."""
    project_root = Path(project_root).resolve()
    id_subs = dict(alloc.id_substitutions)
    path_subs = {spec.source_rel: alloc.dest_rel[spec.old_id] for spec in disc.legacy}

    _collision_preflight(project_root, disc, alloc)

    destinations: list[Destination] = []
    for spec in disc.legacy:
        new_id = id_subs.get(spec.old_id, spec.old_id)
        dest_rel = alloc.dest_rel[spec.old_id]
        local_part = alloc.new_local_part[spec.old_id]
        rendered = _render_destination(spec, alloc, id_subs, path_subs, new_id, dest_rel)
        preimage = hashlib.sha256((project_root / spec.source_rel).read_bytes()).hexdigest()
        destinations.append(
            Destination(
                old_id=spec.old_id,
                new_id=new_id,
                source_rel=spec.source_rel,
                dest_rel=dest_rel,
                number=int(local_part[:4]),
                local_part=local_part,
                rendered_text=rendered,
                preimage_sha256=preimage,
            )
        )

    _validate_batch(project_root, destinations)

    source_rels = frozenset(spec.source_rel for spec in disc.legacy)
    dest_rels = frozenset(alloc.dest_rel[spec.old_id] for spec in disc.legacy)
    exclude = frozenset((project_root / rel) for rel in (source_rels | dest_rels))
    ref_report = plan_reference_rewrite(project_root, id_substitutions=id_subs, path_substitutions=path_subs, exclude=exclude)
    return Transaction(destinations=destinations, ref_report=ref_report, source_rels=source_rels, dest_rels=dest_rels)

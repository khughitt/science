"""`science entity migrate-specs` (S3b) — canonicalize legacy/loose spec docs to numeric entities.

Ships the migration; does NOT flip `spec:` resolution (`_ANNOTATION_REF_PREFIXES` is untouched).
ONE planning authority (`_plan_all`) produces both the flip-readiness report AND the frozen
transaction, so a dry run exercises every refusal a `--apply` would. The design is
`docs/plans/2026-07-18-specs-plans-as-entities-s3b-design.md`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_model.frontmatter import split_frontmatter

from science_tool.entities import (
    _REFERENCE_SCAN_SKIP_DIRS,
    derive_slug,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
)
from science_tool.entity_reservation import propose_number
from science_tool.text_scan import MAX_SCANNABLE_BYTES, TEXT_SUFFIXES

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
    """The NNNN of a FULL conforming `spec:NNNN-slug` id, else None. A prefix-only match (e.g.
    `spec:0007-x/../../outside`) is rejected — `local_part_conforms` requires the whole numeric shape."""
    local = old_id.split(":", 1)[1] if ":" in old_id else old_id
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

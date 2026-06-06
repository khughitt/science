"""One-time migration of legacy doc/ + specs/ entity layouts into entities/.

Pure functions (discover → synthesize → plan → rewrite) plus a `migrate_layout`
orchestrator. Dry-run by default; `--apply` performs git mv + writes.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
import datetime
import re

import yaml

if TYPE_CHECKING:
    from science_tool.graph.sources import ProjectSources

from science_tool.entities import (
    EntityCommandError,
    EntityPathPolicy,
    default_status,
    derive_slug,
    is_markdown_entity_kind,
    load_local_entity_policies,
    local_kind_warnings,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
    singleton_path,
    valid_statuses,
)

_FRONTMATTER = re.compile(r"^---\n(.*?)\n?---\n?(.*)$", re.DOTALL)
# Roots scanned for legacy entities. entities/ is intentionally excluded.
_LEGACY_SCAN_ROOTS = ("doc", "specs")
# Roots walked for in-place reference rewriting (markdown + yaml).
_INPLACE_ROOTS = ("entities", "doc", "specs", "tasks", "research", "knowledge")
# Glob patterns used in the in-place walk (all three are scanned per root).
_INPLACE_GLOBS = ("*.md", "*.yaml", "*.yml")
# Sentinel for "no date derivable" — used as a sort-last key and blocking guard.
# Never written to disk: date-less entities block --apply before any mutation.
_UNDATED_SENTINEL = "9999-99-99"


@dataclass(frozen=True)
class LegacyEntity:
    rel_path: str
    kind: str
    old_id: str | None
    frontmatter: dict
    body: str


def _split_frontmatter(text: str) -> tuple[dict | None, str]:
    match = _FRONTMATTER.match(text)
    if match is None:
        return None, text
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None, match.group(2)  # body without fences, not the full text
    return (data if isinstance(data, dict) else None), match.group(2)


def _discover_with_skips(project_root: Path) -> tuple[list[LegacyEntity], list[str]]:
    results: list[LegacyEntity] = []
    skipped_untyped: list[str] = []
    known = set(markdown_entity_kinds(project_root=project_root))
    dir_to_kind = _project_dir_to_kind(project_root)
    for root_name in _LEGACY_SCAN_ROOTS:
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(project_root).as_posix()
            if "templates" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            frontmatter, body = _split_frontmatter(text)
            kind, needs_signal = _infer_kind(rel, frontmatter, known_kinds=known, dir_to_kind=dir_to_kind)
            if kind is None:
                continue
            if needs_signal and not _has_entity_signal(frontmatter):
                skipped_untyped.append(rel)  # prose doc at a real root, no id/type — not an entity
                continue
            if not is_markdown_entity_kind(kind, project_root=project_root):
                continue
            old_id = None
            if frontmatter is not None:
                raw_id = frontmatter.get("id")
                old_id = raw_id if isinstance(raw_id, str) else None
            results.append(
                LegacyEntity(rel_path=rel, kind=kind, old_id=old_id, frontmatter=frontmatter or {}, body=body)
            )
    return results, sorted(skipped_untyped)


def discover_legacy_entities(project_root: Path) -> list[LegacyEntity]:
    return _discover_with_skips(project_root)[0]


# Specific legacy file paths whose kind cannot be inferred from the parent dir.
# `doc/reports/synthesis.md` is the legacy synthesis singleton: its parent dir is
# "reports", which the generic map would misclassify as `report`. Validation
# already treats this exact path as synthesis (discussions.py), so the migrator
# must agree.
_PATH_KIND_OVERRIDES: dict[str, str] = {
    "doc/reports/synthesis.md": "synthesis",
}


def _has_entity_signal(frontmatter: dict | None) -> bool:
    """True iff the frontmatter carries a non-empty entity signal (id/type/kind).
    Empty strings, None, and other falsy values are not considered signals."""
    if not frontmatter:
        return False
    return any(frontmatter.get(k) for k in ("id", "type", "kind"))


def _infer_kind(
    rel_path: str,
    frontmatter: dict | None,
    *,
    known_kinds: set[str],
    dir_to_kind: dict[str, str],
) -> tuple[str | None, bool]:
    """Return (kind, needs_signal). needs_signal is True only for the directory
    fallback path; explicit type/kind/known-id-prefix and the by-path override
    are authoritative and need no extra signal."""
    if frontmatter is not None:
        value = frontmatter.get("type") or frontmatter.get("kind")
        if isinstance(value, str) and value:
            return value, False  # explicit type wins
        raw_id = frontmatter.get("id")
        if isinstance(raw_id, str) and ":" in raw_id:
            prefix = raw_id.split(":", 1)[0]
            if prefix in known_kinds:
                return prefix, False  # id-prefix beats directory name for foreign-dir files
    if rel_path in _PATH_KIND_OVERRIDES:
        return _PATH_KIND_OVERRIDES[rel_path], False  # synthesis singleton by path
    parent = Path(rel_path).parent.as_posix()
    dir_kind = dir_to_kind.get(parent)
    if dir_kind is not None:
        return dir_kind, True  # dir fallback: requires an entity signal (decision 4)
    return None, False


def _project_dir_to_kind(project_root: Path) -> dict[str, str]:
    """Full relative parent-path -> kind for the directory-name discovery fallback.

    Unions: pre-v3 legacy source roots, entities/<dir> destination roots (re-run
    safety), and each local kind's declared home. Keyed on the FULL relative path
    (not the bare segment) so nested dirs that merely share a name are not matched."""
    mapping = {**_LEGACY_ROOT_TO_KIND, **_DEST_ROOT_TO_KIND}
    for kind, policy in load_local_entity_policies(project_root).items():
        if policy.strategy != "singleton":
            mapping[policy.root.as_posix()] = kind
    return mapping


# Pre-v3 legacy source roots -> kind, keyed on the FULL relative parent path so a
# nested dir whose bare name happens to match (doc/background/papers) is NOT swept.
# One entry per numeric/citekey core kind, derived from the pre-v3 layout.
# NOTE: synthesis appears here defensively (strategy=numeric); in practice it is
# discovered exclusively via _PATH_KIND_OVERRIDES (doc/reports/synthesis.md).
# If a new core kind is added: add its pre-v3 legacy root here ONLY if it
# existed on disk under doc/ or specs/ before the v3 migration; new kinds
# introduced after migration don't need a legacy entry (_DEST_ROOT_TO_KIND
# covers their entities/ home automatically via the SSOT derivation).
_LEGACY_ROOT_TO_KIND: dict[str, str] = {
    "doc/papers": "paper",
    "doc/questions": "question",
    "doc/topics": "topic",
    "doc/interpretations": "interpretation",
    "doc/reports": "report",
    "doc/methods": "method",
    "doc/plans": "plan",
    "doc/pre-registrations": "pre-registration",
    "doc/discussions": "discussion",
    "doc/themes": "theme",
    "doc/searches": "search",
    "doc/evidence-lines": "evidence-line",
    "doc/findings": "finding",
    "doc/inquiries": "inquiry",
    "doc/observations": "observation",
    "doc/mechanisms": "mechanism",
    # synthesis appears here defensively (strategy=numeric); in practice it is
    # discovered exclusively via _PATH_KIND_OVERRIDES (doc/reports/synthesis.md).
    # Under the entity-signal gate, a stray doc/synthesis/<foo>.md with no id/type
    # lands in skipped_untyped, not swept in as an entity.
    "doc/synthesis": "synthesis",
    "specs/hypotheses": "hypothesis",
    "specs/propositions": "proposition",
}

# Destination roots (entities/<dir>) -> kind, for re-running on a partly-migrated
# tree. Derived from the policy table (SSOT) so every numeric/citekey kind's home
# is covered; singletons (no per-kind dir) are excluded.
_DEST_ROOT_TO_KIND: dict[str, str] = {
    resolve_path_policy(kind).root.as_posix(): kind
    for kind in markdown_entity_kinds()
    if resolve_path_policy(kind).strategy != "singleton"
}

_DATE_HEADER_RE = re.compile(r"^\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_STATUS_HEADER_RE = re.compile(r"^\*\*Status:\*\*\s*(.+)$", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
# FIX 3: captures a leading YYYY-MM-DD date from a filename stem so that files
# like `2026-05-30-paper-triage-manifest.md` can supply their own `created` date
# even when no frontmatter `created` field and no `**Date:**` prose header exist.
_DATE_PREFIX_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[-.]|$)")
# Frontmatter values: accept plain dates AND ISO timestamps (no suffix required),
# unlike _DATE_PREFIX_DATE_RE which anchors on filename-stem date prefixes.
_LEADING_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _leading_date(value: object) -> str | None:
    """Extract and validate a leading YYYY-MM-DD from a date or ISO-timestamp.

    `created:` is modeled as a date, but `generated_at:` is an ISO *timestamp*
    (2026-04-28T12:00:00Z). Take the leading date component and confirm it is a
    real calendar date; return None (fall through) when there is none."""
    if not value:
        return None
    m = _LEADING_DATE_RE.match(str(value))
    if m is None:
        return None
    try:
        datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None
    return m.group(1)


def _fallback_created(entity: "LegacyEntity") -> str:
    """created fallback: frontmatter created -> generated_at -> committed ->
    filename YYYY-MM-DD prefix -> sentinel. Each frontmatter source is normalized
    to a real date via `_leading_date`; a value with no parseable leading date is
    skipped rather than copied raw.

    (synthesize_frontmatter still prefers a body **Date:** header over this fallback.)
    """
    for key in ("created", "generated_at", "committed"):
        candidate = _leading_date(entity.frontmatter.get(key))
        if candidate:
            return candidate
    m = _DATE_PREFIX_DATE_RE.match(Path(entity.rel_path).stem)
    if m:
        return m.group(1)
    return _UNDATED_SENTINEL


def synthesize_frontmatter(*, kind: str, body: str, fallback_created: str, project_root: Path | None = None) -> dict:
    """Build a minimal valid frontmatter dict from prose headers + fallbacks.

    Used for legacy files that have no (or partial) YAML frontmatter so they
    become loadable before reference rewriting.
    """
    date_match = _DATE_HEADER_RE.search(body)
    created = date_match.group(1) if date_match else fallback_created
    status_match = _STATUS_HEADER_RE.search(body)
    parsed_status = status_match.group(1).strip() if status_match else ""
    allowed = valid_statuses(kind, project_root=project_root)
    if allowed is None:
        # Open set (local kind, no declared vocabulary): accept any prose status,
        # else the per-kind default.
        status = parsed_status or default_status(kind, project_root=project_root)
    else:
        # Closed set: accept a prose **Status:** value ONLY if it is in the kind's
        # controlled vocabulary; otherwise use the per-kind default (NOT a blanket
        # "active", which is invalid for hypothesis/proposition/evidence-line). The
        # original prose line stays in the body, so nothing is lost.
        status = parsed_status if parsed_status in allowed else default_status(kind, project_root=project_root)
    title_match = _H1_RE.search(body)
    title = title_match.group(1).strip() if title_match else f"Untitled {kind}"
    return {
        "type": kind,
        "title": title,
        "status": status,
        "created": created,
        "updated": created,
    }


def ensure_frontmatter(entity: "LegacyEntity", *, fallback_created: str, project_root: Path | None = None) -> dict:
    """Return a complete frontmatter dict, synthesizing missing fields."""
    base = synthesize_frontmatter(
        kind=entity.kind, body=entity.body, fallback_created=fallback_created, project_root=project_root
    )
    base.update({k: v for k, v in entity.frontmatter.items() if v not in (None, "")})
    base["type"] = entity.kind  # canonicalize: type wins over legacy `kind`
    base.pop("kind", None)
    return base


# ---------------------------------------------------------------------------
# Planning layer: assign target paths and build the old→new id map
# ---------------------------------------------------------------------------

# IMPORTANT: date prefix is tried BEFORE the numeric prefix, so 2026-05-23-foo
# yields slug "foo" (not "05-23-foo" from the numeric regex matching "2026").
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.*)$")  # 2026-05-23-foo
_LEGACY_LOCAL_RE = re.compile(r"^(?:[A-Za-z]+)?(\d+)-(.*)$")  # h01-foo, q5-foo, 0003-foo

# Known legacy locations of the two singletons (no per-kind dir / no type field).
_SINGLETON_LEGACY_PATHS: dict[str, tuple[str, ...]] = {
    "research-question": ("specs/research-question.md", "doc/research-question.md"),
    "claim-registry": ("specs/claim-registry.yaml",),
}


@dataclass(frozen=True)
class Move:
    old_rel_path: str
    new_rel_path: str
    old_id: str | None
    new_id: str
    kind: str


@dataclass(frozen=True)
class SingletonMove:
    old_rel_path: str
    new_rel_path: str


@dataclass
class MigrationPlan:
    moves: list[Move] = field(default_factory=list)
    singletons: list[SingletonMove] = field(default_factory=list)
    id_map: dict[str, str] = field(default_factory=dict)  # old_id -> new_id
    collisions: list[dict] = field(default_factory=list)  # blocking; reported
    # Tracks stem-alias keys added to id_map so alias-vs-alias conflicts can be
    # detected without confusing them with real old_id mappings (which always win).
    _stem_alias_sources: dict[str, str] = field(default_factory=dict)  # alias -> new_id that claimed it


def _is_fallback_title(title: str, kind: str) -> bool:
    """True iff `title` is the synthesized fallback produced when no H1 is found."""
    return title == f"Untitled {kind}"


def _slug_from_legacy(entity: "LegacyEntity", frontmatter: dict) -> str:
    """Derive a canonical slug for a legacy entity.

    Priority:
    1. Strip a date prefix (2026-05-23-foo → "foo").
    2. Strip a legacy numeric/letter prefix (h01-foo, q5-foo → "foo"), provided
       the remainder is long enough to make a valid slug.
    3. Synthesized/merged title when it is a REAL title (not the "Untitled <kind>"
       fallback produced when the file has no H1 heading).
    4. Filename stem directly (aging-early, new-one → as-is).
    5. "Untitled <kind>" fallback title (last resort).

    `derive_slug` raises EntityCommandError for slugs shorter than 2 chars; we
    guard against that by falling through to the next candidate.

    NOTE: this function is NOT called for conformant stems (0003-x, 0005-foo-bar);
    those keep their existing stem verbatim via ``_local_from_conformant_stem``.
    """
    stem = Path(entity.rel_path).stem
    # 1. Date prefix — must be tried before legacy-number because "2026-05-23-foo"
    #    has "2026" which the LEGACY_LOCAL_RE would mis-parse as a sequence number.
    m = _DATE_PREFIX_RE.match(stem)
    if m is not None and m.group(1):
        try:
            return derive_slug(m.group(1))
        except EntityCommandError:
            pass  # remainder too short — fall through

    # 2. Legacy numeric/letter prefix (h01-foo, q5-foo).
    m = _LEGACY_LOCAL_RE.match(stem)
    if m is not None and m.group(2):
        try:
            return derive_slug(m.group(2))
        except EntityCommandError:
            pass  # remainder too short — fall through

    # 3. Real synthesized/merged title (H1 header found in body).
    title = frontmatter.get("title")
    if title and not _is_fallback_title(str(title), entity.kind):
        try:
            return derive_slug(str(title))
        except EntityCommandError:
            pass

    # 4. Stem itself (aging-early, new-one, etc.).
    try:
        return derive_slug(stem)
    except EntityCommandError:
        pass

    # Final fallback: the synthesized title is always present and >= 2 chars.
    return derive_slug(str(title)) if title else derive_slug(f"untitled-{entity.kind}")


def plan_migration(project_root: Path) -> MigrationPlan:
    plan = MigrationPlan()
    _plan_singletons(project_root, plan)

    entities = discover_legacy_entities(project_root)
    # Singleton-kind files (research-question, claim-registry) are relocated by
    # _plan_singletons via explicit paths — never numbered or frontmatter-synthesized
    # here. They also have no status vocabulary, so synthesize_frontmatter would
    # KeyError on them. Exclude them from the move-planning set entirely.
    movable = [e for e in entities if resolve_path_policy(e.kind, project_root=project_root).strategy != "singleton"]
    # Synthesize complete frontmatter BEFORE planning so created/title/slug are
    # correct even for prose-header (frontmatterless) files.
    normalized: dict[str, dict] = {
        e.rel_path: ensure_frontmatter(e, fallback_created=_fallback_created(e), project_root=project_root)
        for e in movable
    }
    by_kind: dict[str, list[LegacyEntity]] = {}
    for entity in movable:
        by_kind.setdefault(entity.kind, []).append(entity)

    for kind, items in by_kind.items():
        policy = resolve_path_policy(kind, project_root=project_root)
        if policy.strategy == "singleton":
            # Singleton kinds (research-question, claim-registry) are relocated by
            # _plan_singletons via explicit by-path rules, never numbered. Skip them
            # here so a stray `type: research-question` file is not mis-numbered.
            continue
        if policy.strategy == "citekey":
            for entity in items:
                local = Path(entity.rel_path).stem
                _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)
            continue
        # numeric: preserve conformant numbers; assign the rest in created order.
        ordered = sorted(items, key=lambda e: (str(normalized[e.rel_path]["created"]), e.rel_path))
        taken: set[int] = set()
        # Seed `taken` with numbers ALREADY committed under entities/<kind>/ so a
        # PARTIALLY-migrated project (entities created additively before/after a
        # prior run) never reassigns an occupied number. These pre-existing files
        # are not moves; they only reserve their slots.
        existing_numbers = _existing_entity_numbers(project_root, policy)
        taken |= existing_numbers
        deferred: list[LegacyEntity] = []
        provisional: dict[str, int] = {}
        for entity in ordered:
            stem = Path(entity.rel_path).stem
            # A date-prefixed stem (2026-05-23-foo) technically matches
            # _NUMERIC_LOCAL_PART_RE because "2026" is 4 digits, but it is a
            # calendar date, NOT a sequence number. Always treat such stems as
            # non-conformant so they get assigned a proper NNNN sequence number.
            is_date_stem = _DATE_PREFIX_RE.match(stem) is not None
            if not is_date_stem and local_part_conforms(kind, stem, project_root=project_root):
                number = int(stem.split("-", 1)[0])
                if number in existing_numbers:
                    # A conformant legacy file wants a number an entities/ file
                    # already holds → blocking number collision (manual fix).
                    plan.collisions.append(
                        {
                            "kind": "number",
                            "entity_kind": kind,
                            "number": f"{number:04d}",
                            "sources": [entity.rel_path],
                            "occupied_by": "entities/",
                        }
                    )
                provisional[entity.rel_path] = number
                taken.add(number)  # NB: two pre-conformant 0003-* both keep 3 → collision (detected below)
            else:
                deferred.append(entity)
        nxt = 1
        for entity in deferred:
            while nxt in taken:
                nxt += 1
            provisional[entity.rel_path] = nxt
            taken.add(nxt)
            nxt += 1
        for entity in ordered:
            number = provisional[entity.rel_path]
            stem = Path(entity.rel_path).stem
            is_date_stem = _DATE_PREFIX_RE.match(stem) is not None
            if not is_date_stem and local_part_conforms(kind, stem, project_root=project_root):
                # Conformant stem (e.g. "0003-foo-bar"): keep it verbatim as the
                # local part so IDs and slugs remain stable across re-runs.
                local = stem
            else:
                local = f"{number:04d}-{_slug_from_legacy(entity, normalized[entity.rel_path])}"
            _add_move(plan, entity, f"{policy.root.as_posix()}/{local}.md", f"{kind}:{local}", kind)

    _detect_collisions(plan)
    _detect_disk_collisions(project_root, plan)
    return plan


def _existing_entity_numbers(project_root: Path, policy: EntityPathPolicy) -> set[int]:
    """Numbers already committed under entities/<kind>/ (NNNN-*.md)."""
    directory = project_root / policy.root
    numbers: set[int] = set()
    if directory.is_dir():
        for path in directory.glob("*.md"):
            match = re.match(r"^(\d{4})-", path.name)
            if match is not None:
                numbers.add(int(match.group(1)))
    return numbers


def _detect_disk_collisions(project_root: Path, plan: MigrationPlan) -> None:
    """Flag any planned target path already occupied on disk by a file we are not
    moving (e.g. a pre-existing entities/papers/<citekey>.md or NNNN-*.md). This
    catches partial-migration / re-run cases that the moves-only collision pass
    cannot see."""
    moved_sources = {m.old_rel_path for m in plan.moves} | {s.old_rel_path for s in plan.singletons}
    for new_rel, old_rel in (
        *[(m.new_rel_path, m.old_rel_path) for m in plan.moves],
        *[(s.new_rel_path, s.old_rel_path) for s in plan.singletons],
    ):
        if new_rel in moved_sources:
            continue  # a swap among the files we are moving — handled by path/id checks
        if (project_root / new_rel).exists():
            plan.collisions.append({"kind": "disk", "target": new_rel, "sources": [old_rel]})


def _add_move(plan: MigrationPlan, entity: "LegacyEntity", new_rel: str, new_id: str, kind: str) -> None:
    plan.moves.append(Move(entity.rel_path, new_rel, entity.old_id, new_id, kind))
    if entity.old_id:
        plan.id_map[entity.old_id] = new_id
    # Frontmatterless / prose-header files carry no `old_id`, yet references may
    # still point at them by their old filename stem (e.g. a link to
    # `interpretation:2026-05-23-foo` for a file with no `id:`). Map a
    # filename-derived alias `<kind>:<old-stem>` -> new_id so those refs rewrite
    # instead of being reported unresolved.
    #
    # Safety rules:
    #   - A real old_id mapping always wins; setdefault ensures we never clobber it.
    #   - When TWO stem-alias entries disagree (two legacy scan roots yield the same
    #     stem under the same kind), the alias is AMBIGUOUS: remove it from id_map
    #     entirely and record a blocking collision so Task 4 reports the ref as
    #     UNRESOLVED rather than silently rewriting to the wrong target.
    stem = Path(entity.rel_path).stem
    if stem == kind:
        # Bare kind-word stem (interpretation.md under doc/probes/<date>/): the
        # plain alias `interpretation:interpretation` collides across sibling
        # date dirs. Scope it by the date-prefixed parent dir so each is distinct.
        parent_name = Path(entity.rel_path).parent.name
        date_m = _DATE_PREFIX_DATE_RE.match(parent_name)
        alias_local = f"{date_m.group(1)}-{stem}" if date_m else stem
    else:
        alias_local = stem
    stem_alias = f"{kind}:{alias_local}"
    if stem_alias in plan.id_map:
        # Key already present. Was it set by a prior stem alias or by a real old_id?
        if stem_alias in plan._stem_alias_sources:
            prior_new_id = plan._stem_alias_sources[stem_alias]
            if prior_new_id != new_id:
                # Two stem aliases disagree → ambiguous; remove to force UNRESOLVED.
                plan.id_map.pop(stem_alias)
                plan._stem_alias_sources.pop(stem_alias)
                plan.collisions.append(
                    {
                        "kind": "alias",
                        "alias": stem_alias,
                        "sources": sorted(
                            [
                                entity.rel_path,
                                next(m.old_rel_path for m in plan.moves if m.new_id == prior_new_id),
                            ]
                        ),
                    }
                )
            # else: same alias already maps to the same new_id (idempotent) — leave it.
        # else: a real old_id owns this key — leave it as-is (real mapping wins).
    else:
        plan.id_map[stem_alias] = new_id
        plan._stem_alias_sources[stem_alias] = new_id

    # FIX 1: numeric shortform alias — prose references a numbered entity by its
    # leading token (question:01, hypothesis:h03). Renumbering changes the number,
    # so map the OLD shortform token -> the NEW numeric shortform (question:0001)
    # so prose refs are rewritten consistently. Only for genuine shortform shapes
    # ([letters]+digits), so slug fragments like topic:foo are never mistaken for one.
    new_local = new_id.split(":", 1)[1]
    new_num_match = re.match(r"^(\d{4})$|^(\d{4})-", new_local)
    if entity.old_id and ":" in entity.old_id and new_num_match:
        new_num = new_num_match.group(1) or new_num_match.group(2)
        old_token = entity.old_id.split(":", 1)[1].split("-", 1)[0]
        if re.fullmatch(r"[A-Za-z]*\d+", old_token) and old_token != new_num:
            plan.id_map.setdefault(f"{kind}:{old_token}", f"{kind}:{new_num}")


def _plan_singletons(project_root: Path, plan: MigrationPlan) -> None:
    for kind, candidates in _SINGLETON_LEGACY_PATHS.items():
        target = singleton_path(kind).as_posix()
        for rel in candidates:
            if (project_root / rel).is_file():
                plan.singletons.append(SingletonMove(old_rel_path=rel, new_rel_path=target))
                break  # first existing candidate wins


def _detect_collisions(plan: MigrationPlan) -> None:
    by_path: dict[str, list[str]] = {}
    by_id: dict[str, list[str]] = {}
    by_kind_number: dict[tuple[str, str], list[str]] = {}
    for move in plan.moves:
        by_path.setdefault(move.new_rel_path, []).append(move.old_rel_path)
        by_id.setdefault(move.new_id, []).append(move.old_rel_path)
        # number-hygiene collision: two files keep the SAME number within a kind
        # (e.g. pre-conformant 0003-a.md + 0003-b.md → different ids/paths, but a
        # duplicate number, which by_path/by_id alone would miss).
        local = move.new_id.split(":", 1)[1]
        number_match = re.match(r"^(\d{4})-", local)
        if number_match is not None:
            by_kind_number.setdefault((move.kind, number_match.group(1)), []).append(move.old_rel_path)
    for target, sources in sorted(by_path.items()):
        if len(sources) > 1:
            plan.collisions.append({"kind": "path", "target": target, "sources": sorted(sources)})
    for new_id, sources in sorted(by_id.items()):
        if len(sources) > 1:
            plan.collisions.append({"kind": "id", "new_id": new_id, "sources": sorted(sources)})
    for (kind, number), sources in sorted(by_kind_number.items()):
        if len(sources) > 1:
            plan.collisions.append(
                {
                    "kind": "number",
                    "entity_kind": kind,
                    "number": number,
                    "sources": sorted(sources),
                    "occupied_by": None,
                }
            )


# ---------------------------------------------------------------------------
# Reference-rewriting layer
# ---------------------------------------------------------------------------

# A reference token: <kind>:<local-part>. Legacy local parts may carry a letter
# prefix (q1, h09) or a date (2026-05-23); canonical are NNNN or a citekey.
_REF_TOKEN_RE = re.compile(r"\b([a-z][a-z-]*):([A-Za-z0-9][A-Za-z0-9_.-]*)\b")
# Bare-wikilink shape guard (distinct from _LEGACY_LOCAL_RE, which parses file stems in discovery).
_LEGACY_LOCAL_SHAPE = re.compile(r"^(?:[A-Za-z]+\d+|\d{4}-\d{2}-\d{2})(?:-|$)")
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _strip_code_spans(text: str) -> str:
    """Remove fenced code blocks and inline-code spans so example ids inside
    documentation do not generate reference warnings.

    Note: an *unterminated* fenced block is not stripped, so legacy-shaped tokens
    inside it may produce (harmless, non-blocking) warnings.
    """
    text = _FENCE_RE.sub("", text)
    return _INLINE_CODE_RE.sub("", text)


def _is_placeholder_token(token: str) -> bool:
    """Stub — Unit G replaces this with the real placeholder filter. Returns
    False so every prose token is kept as a warning until Unit G lands."""
    return False


def rewrite_references(
    text: str,
    id_map: dict[str, str],
    *,
    policed_kinds: set[str] | None = None,
    project_root: Path | None = None,
) -> tuple[str, list[str]]:
    """Replace every mapped old id with its new id (longest-first to avoid prefix
    collisions). Returns (rewritten_text, unresolved_legacy_tokens).

    A token that *looks* legacy-shaped but has no mapping is reported in
    `unresolved` rather than left to rot into a dead link. This covers both
    `<kind>:<local>` tokens AND bare `[[<local>]]` wiki-links (no colon).

    `policed_kinds`: when provided, only flag tokens whose kind appears in this
    set as unresolved. Kinds absent from the set (e.g. observation, stored in a
    YAML registry rather than markdown files) are silently skipped. Default None
    preserves existing behaviour (police all managed markdown kinds).
    """
    # Replace longest keys first so question:q10-b is handled before question:q1-b.
    # Lookbehind: don't match mid-token (e.g. inside "question:0001-aging-early").
    # Lookahead: don't match when followed by word chars or hyphen (i.e. the token
    # continues), but DO allow a trailing period (sentence boundary).
    for old_id in sorted(id_map, key=len, reverse=True):
        new_id = id_map[old_id]
        text = re.sub(rf"(?<![\w:.-]){re.escape(old_id)}(?![\w-])", new_id, text)

    unresolved: list[str] = []
    new_ids = set(id_map.values())
    # (a) kind-qualified tokens (covers id:, related:, inline, and [[kind:local]]).
    #     For a kind WE MANAGE, any local part that (1) was not rewritten to a new
    #     id and (2) does not conform to the kind's filename policy is a
    #     stale/dangling reference — this catches plain slugs like
    #     `question:old-slug` that the old legacy-shape heuristic (q##-/date only)
    #     silently kept. External / unmanaged prefixes (urls, ontology ids) and
    #     already-conformant ids are left untouched.
    for match in _REF_TOKEN_RE.finditer(text):
        token, kind, local = match.group(0), match.group(1), match.group(2)
        if token in new_ids:
            continue  # already canonical (a freshly-written new id)
        if not is_markdown_entity_kind(kind, project_root=project_root):
            continue  # external prefix / url / kind we do not govern
        if policed_kinds is not None and kind not in policed_kinds:
            continue  # kind not migrated as markdown (e.g. stored in a YAML registry) — out of scope
        if resolve_path_policy(kind, project_root=project_root).strategy == "singleton":
            continue  # singletons carry no per-instance local part
        if local_part_conforms(kind, local, project_root=project_root):
            continue  # already a valid local part for this kind
        unresolved.append(token)
    # (b) bare wiki-links with NO kind prefix, e.g. [[q01-foo]] / [[2026-05-23-x]].
    #     These cannot be disambiguated to a kind, so they are reported, not rewritten.
    for match in _WIKILINK_RE.finditer(text):
        inner = match.group(1).strip()
        if ":" in inner:
            continue  # kind-qualified — handled by (a)/token replacement above
        if _LEGACY_LOCAL_SHAPE.match(inner):
            unresolved.append(f"[[{inner}]]")
    return text, sorted(set(unresolved))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _git_mv(project_root: Path, old_rel: str, new_rel: str) -> None:
    dest = project_root / new_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "mv", old_rel, new_rel], cwd=project_root, check=True)


def _render(frontmatter: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body


_SIM_PLACEHOLDER_DATE = "2000-01-01"  # simulation-only stand-in for the undated sentinel


def _simulated_postmove_audit_failures(
    project_root: Path,
    plan: MigrationPlan,
    rewritten: dict[str, str],
    singleton_text: dict[str, str],
    inplace_text: dict[str, str],
    undated_new_paths: set[str],
) -> list[dict]:
    """Graph-audit-equivalent validation over a simulated post-move source set.

    Builds the simulated post-move ProjectSources in-memory (markdown_overrides
    inject moved entities at their new entities/<kind>/ paths; manual_aliases is
    augmented with plan.id_map so disk-resident non-markdown sources resolve
    old->new) and runs the existing audit_project_sources, returning its fail rows.

    Loads under strict core schema (the SAME strictness as the post-mutation
    backstop) to preserve parity. Two special cases keep that faithful without
    crashing the dry-run:
      - Undated entities carry the 9999-99-99 sentinel (invalid date) but are
        blocked independently by the undated guard; they are given a valid
        placeholder date in the simulation ONLY, so the post-move set loads and
        inbound refs to them still resolve.
      - A genuinely schema-invalid core entity raises here under strict schema —
        exactly as the post-mutation backstop would. That is surfaced as a
        pre-mutation blocker (no tree mutation) rather than crashing the dry-run.
    """
    from science_tool.graph.migrate import audit_project_sources
    from science_tool.graph.sources import load_project_sources

    merged = {**rewritten, **singleton_text, **inplace_text}
    overrides: dict[str, str] = {}
    for rel, text in merged.items():
        if not rel.endswith(".md"):
            continue
        if rel in undated_new_paths:
            text = text.replace(_UNDATED_SENTINEL, _SIM_PLACEHOLDER_DATE)
        overrides[rel] = text
    try:
        sources = load_project_sources(project_root, overrides)
    except Exception as exc:
        # An unexpected (non-schema) exception is also intentionally converted to a
        # blocker so --apply never proceeds on an unloadable simulated tree.
        return [
            {
                "check": "schema_load_failure",
                "status": "fail",
                "source": "(project sources)",
                "field": "frontmatter",
                "target": str(exc),
                "details": str(exc),
            }
        ]
    # Capture the real mappings.yaml aliases BEFORE injecting plan.id_map so that
    # _dangling_alias_targets only validates project-authored alias entries; plan
    # shortform/stem entries are rewrite tokens, not authoritative references.
    mappings_aliases = dict(sources.manual_aliases)
    sources = sources.model_copy(update={"manual_aliases": {**sources.manual_aliases, **plan.id_map}})
    rows, failed = audit_project_sources(sources)
    audit_fails = [r for r in rows if r.get("status") == "fail"] if failed else []
    return audit_fails + _dangling_alias_targets(sources, mappings_aliases)


def _dangling_alias_targets(sources: "ProjectSources", mappings_aliases: dict[str, str]) -> list[dict]:
    """Alias targets the graph audit silently accepts but that resolve to no
    entity. `audit_project_sources` passes manual_aliases into the resolver but
    never proves each target exists; this closes that gap. Targets are resolved
    THROUGH the simulated alias map (sources.manual_aliases, which includes
    plan.id_map), so a valid target referenced by its OLD id (rewritten to a new
    identity via the injected id_map) is accepted. External (URL/path/go:/mesh:/doi:)
    and meta:* targets are exempt, matching the audit's own acceptance exceptions.

    Only `mappings_aliases` (the real project mappings.yaml entries, before
    plan.id_map injection) are validated — plan.id_map shortform/stem entries are
    rewrite tokens, not authoritative references, and must not be validated here.
    """
    from science_tool.graph.reference_resolution import ReferenceResolver
    from science_tool.graph.sources import is_external_reference, is_metadata_reference

    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    fails: list[dict] = []
    for alias, target in mappings_aliases.items():
        if is_external_reference(target) or is_metadata_reference(target):
            continue
        if resolver.resolve(target).status != "resolved":
            fails.append(
                {
                    "check": "dangling_alias_target",
                    "status": "fail",
                    "source": alias,
                    "field": "aliases",
                    "target": target,
                    "details": f"mappings.yaml alias {alias!r} points to {target!r}, which does not resolve to any entity",
                }
            )
    return fails


def _audit_failures_to_report(rows: list[dict]) -> dict[str, list[str]]:
    """Shape audit fail rows into {source -> sorted unique targets} for the
    report's `unresolved_references` (preserving its dict-of-lists contract)."""
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(str(row.get("source", "?")), []).append(str(row.get("target", "?")))
    return {source: sorted(set(targets)) for source, targets in out.items()}


def migrate_layout(project_root: Path, *, apply: bool) -> dict:
    plan = plan_migration(project_root)
    legacy_entities, skipped_untyped = _discover_with_skips(project_root)
    entities = {e.rel_path: e for e in legacy_entities}
    # FIX 2: restrict unresolved-flagging to kinds actually migrated as markdown.
    # Kinds stored outside markdown (e.g. observation in observations.yaml) produce
    # false positives when prose references them — they are never in the id_map but
    # also cannot be moved, so they should not be policed.
    policed_kinds: set[str] = {e.kind for e in legacy_entities}

    # 1. Frontmatter synthesis (build complete frontmatter per file, with new id).
    rewritten: dict[str, str] = {}  # new_rel_path -> file text (pre ref-rewrite)
    synthesized_fm: dict[str, dict] = {}  # new_rel_path -> fm dict (for undated check)
    for move in plan.moves:
        entity = entities[move.old_rel_path]
        fm = ensure_frontmatter(entity, fallback_created=_fallback_created(entity), project_root=project_root)
        fm["id"] = move.new_id
        rewritten[move.new_rel_path] = _render(fm, entity.body)
        synthesized_fm[move.new_rel_path] = fm

    # 2. Collect undated entities (created == _UNDATED_SENTINEL — no date derivable).
    #    These must be reported in the dry-run and block --apply BEFORE any mutation.
    undated_entities = sorted(
        [
            {"old_rel_path": move.old_rel_path, "new_rel_path": move.new_rel_path}
            for move in plan.moves
            if str(synthesized_fm[move.new_rel_path].get("created")) == _UNDATED_SENTINEL
        ],
        key=lambda d: d["old_rel_path"],
    )

    # Reference rewrite across EVERY project markdown file that can carry an
    # entity id — not only the moved entities. References live in non-entity
    # prose too (reports, notes, research/packages, tasks). The final graph
    # audit (step 4) only inspects STRUCTURED sources (entity frontmatter /
    # relations / bindings), so raw inline `<kind>:local` and `[[…]]` links in
    # bodies would slip through unrewritten. This project-wide pass — plus the
    # unresolved-token report it produces — is that safety net.
    singleton_text: dict[str, str] = {}
    for sm in plan.singletons:
        singleton_text[sm.new_rel_path] = (project_root / sm.old_rel_path).read_text(encoding="utf-8")

    # In-place files: every *.md under the project's content roots that is NOT
    # being moved (moved sources are in `rewritten`, keyed by NEW path; singletons
    # in `singleton_text`). Covers pre-existing entities/ files, doc/ prose,
    # research/packages, and tasks. Templates and .git are skipped.
    moved_sources = {m.old_rel_path for m in plan.moves} | {s.old_rel_path for s in plan.singletons}
    inplace_text: dict[str, str] = {}
    for root_name in _INPLACE_ROOTS:
        root = project_root / root_name
        if not root.is_dir():
            continue
        paths = sorted(p for g in _INPLACE_GLOBS for p in root.rglob(g))
        for path in paths:
            if "templates" in path.parts:
                continue
            rel = path.relative_to(project_root).as_posix()
            if rel in moved_sources:
                continue  # handled via `rewritten` at its new path
            inplace_text[rel] = path.read_text(encoding="utf-8")

    # Full-text rewrite (produces the content --apply will write) + a separate
    # code-stripped pass that feeds the non-blocking prose-warning bucket.
    unresolved_warnings: dict[str, list[str]] = {}
    for bucket in (rewritten, singleton_text, inplace_text):
        for rel, text in list(bucket.items()):
            out, _ = rewrite_references(text, plan.id_map, policed_kinds=policed_kinds, project_root=project_root)
            bucket[rel] = out
            if rel.endswith("mappings.yaml"):
                # Rewrite already applied above; alias SOURCE keys are definitions,
                # not refs. Alias TARGETS are validated separately (see _dangling_alias_targets).
                continue
            _, warn_tokens = rewrite_references(
                _strip_code_spans(text), plan.id_map, policed_kinds=policed_kinds, project_root=project_root
            )
            warn_tokens = [t for t in warn_tokens if not _is_placeholder_token(t)]
            if warn_tokens:
                unresolved_warnings[rel] = warn_tokens

    # Blocking is graph-audit-equivalent validation over the simulated post-move
    # source set — the SAME check the post-mutation backstop runs, moved earlier.
    structural_failures = _simulated_postmove_audit_failures(
        project_root,
        plan,
        rewritten,
        singleton_text,
        inplace_text,
        {d["new_rel_path"] for d in undated_entities},
    )

    report = {
        "moves": [vars(m) for m in plan.moves],
        "singletons": [vars(s) for s in plan.singletons],
        "id_map": plan.id_map,
        "collisions": plan.collisions,
        "unresolved_references": _audit_failures_to_report(structural_failures),
        "unresolved_warnings": unresolved_warnings,
        "local_kind_warnings": local_kind_warnings(project_root),
        "skipped_untyped": skipped_untyped,
        "undated_entities": undated_entities,
        "applied": apply,
    }

    if not apply:
        return report

    # Pre-mutation guards — raise cleanly with no tree modification.
    if plan.collisions:
        raise ValueError(f"collisions block --apply: {plan.collisions}")
    if structural_failures:
        raise ValueError(
            f"unresolved structural references block --apply "
            f"(simulated post-move graph audit): {structural_failures[:10]}"
        )
    if undated_entities:
        raise ValueError(
            f"undated entities block --apply (add a **Date:** header or frontmatter "
            f"created: to each, then re-run): {undated_entities}"
        )

    # 3+4. git mv + writes + graph validation — wrapped so ANY post-mutation failure
    #      carries uniform rollback guidance.
    try:
        # 3. git mv + write rewritten content (entities, singletons, inplace).
        for move in plan.moves:
            _git_mv(project_root, move.old_rel_path, move.new_rel_path)
            (project_root / move.new_rel_path).write_text(rewritten[move.new_rel_path], encoding="utf-8")
        for sm in plan.singletons:
            _git_mv(project_root, sm.old_rel_path, sm.new_rel_path)
            (project_root / sm.new_rel_path).write_text(singleton_text[sm.new_rel_path], encoding="utf-8")
        for rel, text in inplace_text.items():
            (project_root / rel).write_text(text, encoding="utf-8")

        # 4. Final graph validation — token rewriting can miss semantic references, so
        #    load the migrated tree and audit it. Fail loud (do NOT bump layout_version)
        #    if anything fails to resolve.
        from science_tool.graph.migrate import audit_project_sources
        from science_tool.graph.sources import load_project_sources

        rows, failed = audit_project_sources(load_project_sources(project_root))
        if failed:
            bad = [r for r in rows if r.get("status") == "fail"]
            raise ValueError(f"post-migration graph validation failed with {len(bad)} issue(s): {bad[:10]}")
    except Exception as exc:
        raise ValueError(
            "science entities migrate --apply failed after the working tree was modified; "
            "run `git restore .` (and `git restore --staged .`) or reset the branch to roll back. "
            f"Cause: {exc}"
        ) from exc

    # 5. Only after a clean audit: bump layout_version to 3.
    manifest_path = project_root / "science.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    manifest["layout_version"] = 3
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    report["graph_validation"] = "passed"
    return report

"""One-time migration of legacy doc/ + specs/ entity layouts into entities/.

Pure functions (discover → synthesize → plan → rewrite) plus a `migrate_layout`
orchestrator. Dry-run by default; `--apply` performs git mv + writes.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml

from science_tool.entities import (
    EntityCommandError,
    EntityPathPolicy,
    default_status,
    derive_slug,
    is_markdown_entity_kind,
    local_part_conforms,
    markdown_entity_kinds,
    resolve_path_policy,
    singleton_path,
    valid_statuses,
)

_FRONTMATTER = re.compile(r"^---\n(.*?)\n?---\n?(.*)$", re.DOTALL)
# Roots scanned for legacy entities. entities/ is intentionally excluded.
_LEGACY_SCAN_ROOTS = ("doc", "specs")
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
        return None, match.group(2)   # body without fences, not the full text
    return (data if isinstance(data, dict) else None), match.group(2)


def discover_legacy_entities(project_root: Path) -> list[LegacyEntity]:
    results: list[LegacyEntity] = []
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
            kind = _infer_kind(rel, frontmatter)
            if kind is None or not is_markdown_entity_kind(kind):
                continue
            old_id = None
            if frontmatter is not None:
                raw_id = frontmatter.get("id")
                old_id = raw_id if isinstance(raw_id, str) else None
            results.append(
                LegacyEntity(rel_path=rel, kind=kind, old_id=old_id, frontmatter=frontmatter or {}, body=body)
            )
    return results


# Specific legacy file paths whose kind cannot be inferred from the parent dir.
# `doc/reports/synthesis.md` is the legacy synthesis singleton: its parent dir is
# "reports", which the generic map would misclassify as `report`. Validation
# already treats this exact path as synthesis (discussions.py), so the migrator
# must agree.
_PATH_KIND_OVERRIDES: dict[str, str] = {
    "doc/reports/synthesis.md": "synthesis",
}


def _infer_kind(rel_path: str, frontmatter: dict | None) -> str | None:
    if frontmatter is not None:
        value = frontmatter.get("type") or frontmatter.get("kind")
        if isinstance(value, str) and value:
            return value
    # Frontmatterless file: explicit by-path override first, then the parent
    # directory name (singularized) via the derived map.
    if rel_path in _PATH_KIND_OVERRIDES:
        return _PATH_KIND_OVERRIDES[rel_path]
    parent = Path(rel_path).parent.name
    return _DIR_TO_KIND.get(parent)


# Legacy directory name → kind, for frontmatterless files. DERIVED from the
# policy table (SSOT) so EVERY numeric/citekey kind's plural directory is covered
# — including evidence-lines, reports, plans, searches, methods, and
# pre-registrations that a hand-written map would silently omit (and thereby
# strand valid legacy entities through cutover). Singletons have no per-kind dir,
# so they are excluded.
_DIR_TO_KIND: dict[str, str] = {
    resolve_path_policy(kind).root.name: kind
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


def _fallback_created(entity: "LegacyEntity") -> str:
    """created fallback: frontmatter created -> filename YYYY-MM-DD prefix -> sentinel.

    (synthesize_frontmatter still prefers a body **Date:** header over this fallback.)
    """
    fm_created = entity.frontmatter.get("created")
    if fm_created:
        return str(fm_created)
    m = _DATE_PREFIX_DATE_RE.match(Path(entity.rel_path).stem)
    if m:
        return m.group(1)
    return _UNDATED_SENTINEL


def synthesize_frontmatter(*, kind: str, body: str, fallback_created: str) -> dict:
    """Build a minimal valid frontmatter dict from prose headers + fallbacks.

    Used for legacy files that have no (or partial) YAML frontmatter so they
    become loadable before reference rewriting.
    """
    date_match = _DATE_HEADER_RE.search(body)
    created = date_match.group(1) if date_match else fallback_created
    # Status: accept a prose **Status:** value ONLY if it is in the kind's
    # controlled vocabulary; otherwise use the per-kind default (NOT a blanket
    # "active", which is invalid for hypothesis/proposition/evidence-line). The
    # original prose line stays in the body, so nothing is lost.
    status_match = _STATUS_HEADER_RE.search(body)
    parsed_status = status_match.group(1).strip() if status_match else ""
    status = parsed_status if parsed_status in valid_statuses(kind) else default_status(kind)
    title_match = _H1_RE.search(body)
    title = title_match.group(1).strip() if title_match else f"Untitled {kind}"
    return {
        "type": kind,
        "title": title,
        "status": status,
        "created": created,
        "updated": created,
    }


def ensure_frontmatter(entity: "LegacyEntity", *, fallback_created: str) -> dict:
    """Return a complete frontmatter dict, synthesizing missing fields."""
    base = synthesize_frontmatter(kind=entity.kind, body=entity.body, fallback_created=fallback_created)
    base.update({k: v for k, v in entity.frontmatter.items() if v not in (None, "")})
    base["type"] = entity.kind  # canonicalize: type wins over legacy `kind`
    base.pop("kind", None)
    return base


# ---------------------------------------------------------------------------
# Planning layer: assign target paths and build the old→new id map
# ---------------------------------------------------------------------------

# IMPORTANT: date prefix is tried BEFORE the numeric prefix, so 2026-05-23-foo
# yields slug "foo" (not "05-23-foo" from the numeric regex matching "2026").
_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(.*)$")     # 2026-05-23-foo
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
    movable = [e for e in entities if resolve_path_policy(e.kind).strategy != "singleton"]
    # Synthesize complete frontmatter BEFORE planning so created/title/slug are
    # correct even for prose-header (frontmatterless) files.
    normalized: dict[str, dict] = {
        e.rel_path: ensure_frontmatter(e, fallback_created=_fallback_created(e))
        for e in movable
    }
    by_kind: dict[str, list[LegacyEntity]] = {}
    for entity in movable:
        by_kind.setdefault(entity.kind, []).append(entity)

    for kind, items in by_kind.items():
        policy = resolve_path_policy(kind)
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
            if not is_date_stem and local_part_conforms(kind, stem):
                number = int(stem.split("-", 1)[0])
                if number in existing_numbers:
                    # A conformant legacy file wants a number an entities/ file
                    # already holds → blocking number collision (manual fix).
                    plan.collisions.append(
                        {"kind": "number", "entity_kind": kind, "number": f"{number:04d}",
                         "sources": [entity.rel_path], "occupied_by": "entities/"}
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
            if not is_date_stem and local_part_conforms(kind, stem):
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
    stem_alias = f"{kind}:{Path(entity.rel_path).stem}"
    if stem_alias in plan.id_map:
        # Key already present. Was it set by a prior stem alias or by a real old_id?
        if stem_alias in plan._stem_alias_sources:
            prior_new_id = plan._stem_alias_sources[stem_alias]
            if prior_new_id != new_id:
                # Two stem aliases disagree → ambiguous; remove to force UNRESOLVED.
                plan.id_map.pop(stem_alias)
                plan._stem_alias_sources.pop(stem_alias)
                plan.collisions.append({
                    "kind": "alias",
                    "alias": stem_alias,
                    "sources": sorted([entity.rel_path,
                                       next(m.old_rel_path for m in plan.moves
                                            if f"{m.kind}:{Path(m.old_rel_path).stem}" == stem_alias
                                            and m.new_id == prior_new_id)]),
                })
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
            plan.collisions.append({"kind": "number", "entity_kind": kind, "number": number,
                                    "sources": sorted(sources), "occupied_by": None})


# ---------------------------------------------------------------------------
# Reference-rewriting layer
# ---------------------------------------------------------------------------

# A reference token: <kind>:<local-part>. Legacy local parts may carry a letter
# prefix (q1, h09) or a date (2026-05-23); canonical are NNNN or a citekey.
_REF_TOKEN_RE = re.compile(r"\b([a-z][a-z-]*):([A-Za-z0-9][A-Za-z0-9_.-]*)\b")
# Bare-wikilink shape guard (distinct from _LEGACY_LOCAL_RE, which parses file stems in discovery).
_LEGACY_LOCAL_SHAPE = re.compile(r"^(?:[A-Za-z]+\d+|\d{4}-\d{2}-\d{2})(?:-|$)")
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def rewrite_references(
    text: str,
    id_map: dict[str, str],
    *,
    policed_kinds: set[str] | None = None,
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
        if not is_markdown_entity_kind(kind):
            continue  # external prefix / url / kind we do not govern
        if policed_kinds is not None and kind not in policed_kinds:
            continue  # kind not migrated as markdown (e.g. stored in a YAML registry) — out of scope
        if resolve_path_policy(kind).strategy == "singleton":
            continue  # singletons carry no per-instance local part
        if local_part_conforms(kind, local):
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


def migrate_layout(project_root: Path, *, apply: bool) -> dict:
    plan = plan_migration(project_root)
    legacy_entities = list(discover_legacy_entities(project_root))
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
        fm = ensure_frontmatter(entity, fallback_created=_fallback_created(entity))
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
    for root_name in ("entities", "doc", "specs", "tasks", "research"):
        root = project_root / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if "templates" in path.parts:
                continue
            rel = path.relative_to(project_root).as_posix()
            if rel in moved_sources:
                continue  # handled via `rewritten` at its new path
            inplace_text[rel] = path.read_text(encoding="utf-8")

    all_unresolved: dict[str, list[str]] = {}
    for bucket in (rewritten, singleton_text, inplace_text):
        for rel, text in list(bucket.items()):
            out, unresolved = rewrite_references(text, plan.id_map, policed_kinds=policed_kinds)
            bucket[rel] = out
            if unresolved:
                all_unresolved[rel] = unresolved

    report = {
        "moves": [vars(m) for m in plan.moves],
        "singletons": [vars(s) for s in plan.singletons],
        "id_map": plan.id_map,
        "collisions": plan.collisions,
        "unresolved_references": all_unresolved,
        "undated_entities": undated_entities,
        "applied": apply,
    }

    if not apply:
        return report

    # Pre-mutation guards — raise cleanly with no tree modification.
    if plan.collisions:
        raise ValueError(f"collisions block --apply: {plan.collisions}")
    if all_unresolved:
        raise ValueError(f"unresolved references block --apply: {all_unresolved}")
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
            raise ValueError(
                f"post-migration graph validation failed with {len(bad)} issue(s): {bad[:10]}"
            )
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

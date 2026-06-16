# science/src/science_tool/consolidate.py
"""Entity consolidation — Tier 3 *apply* half (P4).

`scaffold_digest` mints a live `cluster-digest` synthesis entity carrying one typed
`sci:consolidates` authored relation per member; `apply_consolidation` stamps each
member `status: archived` + `consolidated_into`, relocates it via the P3 archive
machinery, and appends an index row. The digest stays live.

This is the apply counterpart to the read-only detector in `consolidation.py`; the
two never import each other.
"""
from __future__ import annotations

from pathlib import Path

from science_tool.archive import (
    ArchiveRow,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
    _relocate_rows,
)
from science_tool.entities import (
    EntityLocation,
    _atomic_replace_text,
    _parse_markdown_file,
    _render_markdown,
    create_entity,
    find_entity,
    valid_statuses,
)

CONSOLIDATES_PREDICATE = "sci:consolidates"
CLUSTER_DIGEST_REPORT_KIND = "cluster-digest"
SYNTHESIS_KIND = "synthesis"


class ConsolidateError(Exception):
    """Raised on an invalid or unsafe consolidate operation (fail-loud)."""


def _is_consolidatable(project_root: Path, kind: str) -> bool:
    """A kind is consolidatable iff its status vocab is open (None) or includes
    `archived`. A closed vocab lacking `archived` fails loud (no auto-patch)."""
    vs = valid_statuses(kind, project_root=project_root)
    return vs is None or "archived" in vs


def _resolve_member(project_root: Path, eid: str) -> EntityLocation:
    try:
        return find_entity(project_root, eid)
    except Exception as exc:  # find_entity raises when the ref is unknown
        raise ConsolidateError(f"member {eid!r} is not a known live entity") from exc


def _validate_members(
    project_root: Path, member_ids: list[str], digest_id: str
) -> list[EntityLocation]:
    if not member_ids:
        raise ConsolidateError("no members supplied to consolidate")
    idx = load_archive_index(project_root)
    locs: list[EntityLocation] = []
    seen: set[str] = set()
    for eid in member_ids:
        if eid == digest_id:
            raise ConsolidateError(f"the digest id {digest_id!r} cannot be one of its own members")
        if eid in seen:
            raise ConsolidateError(f"duplicate member {eid!r}")
        seen.add(eid)
        if eid in idx.active_by_id:
            raise ConsolidateError(f"member {eid!r} is already archived")
        loc = _resolve_member(project_root, eid)
        if not _is_consolidatable(project_root, loc.kind):
            raise ConsolidateError(
                f"member {eid!r} of kind {loc.kind!r} has a closed status vocabulary lacking "
                f"'archived'; add 'archived' to that kind's statuses before consolidating"
            )
        locs.append(loc)
    return locs


def scaffold_digest(
    project_root: Path,
    *,
    digest_id: str,
    member_ids: list[str],
    title: str,
) -> dict:
    """Mint a live cluster-digest synthesis entity (create-then-rewrite, atomic)."""
    project_root = Path(project_root).resolve()
    _validate_members(project_root, member_ids, digest_id)
    # The digest id must not collide with an ACTIVE archived id/alias. create_entity
    # only guards against a live destination path, so without this an archived id
    # could be reborn as a live digest with the same canonical id (validate would
    # only catch it after the bad state was written).
    if digest_id in load_archive_index(project_root).resolvable_ids():
        raise ConsolidateError(
            f"digest id {digest_id!r} collides with an archived entity id/alias; "
            "choose a fresh id or unarchive the colliding entity first"
        )

    result = create_entity(project_root, SYNTHESIS_KIND, title, entity_id=digest_id)
    path = result.path
    try:
        fm, body = _parse_markdown_file(path)
        fm["report_kind"] = CLUSTER_DIGEST_REPORT_KIND
        fm["relations"] = [
            {"predicate": CONSOLIDATES_PREDICATE, "target": m} for m in member_ids
        ]
        _atomic_replace_text(path, _render_markdown(fm, body))
        # Re-validate: the rewritten file must still load as an entity.
        find_entity(project_root, digest_id)
    except Exception:
        # Scaffold rollback: the digest file is brand-new this command — remove it.
        path.unlink(missing_ok=True)
        raise
    return {
        "digest_id": digest_id,
        "digest_path": str(path),
        "members": list(member_ids),
    }

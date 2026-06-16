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

from collections.abc import Mapping
from pathlib import Path
from typing import Any

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
    """Whether `kind` can be consolidated: its status vocab is open (None) or
    includes `archived`. A closed vocab lacking `archived` returns False — the
    caller (`_validate_members`) is what fails loud on it (no auto-patch)."""
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


def consolidates_targets(frontmatter: Mapping[str, Any]) -> list[str]:
    """Member ids = targets of a digest's `sci:consolidates` authored relations,
    read off its frontmatter dict (the shape `scaffold_digest` writes)."""
    targets: list[str] = []
    relations = frontmatter.get("relations") or []
    for rel in relations:
        if isinstance(rel, dict) and rel.get("predicate") == CONSOLIDATES_PREDICATE:
            target = rel.get("target")
            if isinstance(target, str):
                targets.append(target)
    return targets


def apply_consolidation(
    project_root: Path,
    digest_id: str,
    *,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    """Demote + relocate the digest's consolidated members (report, then --apply).

    Per-member transaction: snapshot bytes -> rewrite frontmatter (status/consolidated_into)
    -> relocate via _relocate_rows. On any exception, restore the snapshotted bytes at the
    live original_path (the move-rollback / un-executed move leaves the file there).

    Members are committed one at a time and each member is atomic, but the loop is
    NOT all-or-nothing: if member N fails, members 1..N-1 remain archived+indexed
    while member N (and beyond) are untouched. The digest still lists every member,
    so the operation is not auto-resumable — recovery is to `entities unarchive` the
    already-archived members (or hand-fix) and re-run, or to leave the partial
    consolidation and adjust the digest. No index drift or data loss occurs either way."""
    project_root = Path(project_root).resolve()
    digest = find_entity(project_root, digest_id)
    if digest.frontmatter.get("report_kind") != CLUSTER_DIGEST_REPORT_KIND:
        raise ConsolidateError(f"{digest_id!r} is not a cluster-digest (report_kind)")
    member_ids = consolidates_targets(digest.frontmatter)
    if not member_ids:
        raise ConsolidateError(f"{digest_id!r} has no sci:consolidates relation entries")
    locs = _validate_members(project_root, member_ids, digest_id)

    report: dict = {
        "digest_id": digest_id,
        "members": [loc.entity_id for loc in locs],
        "destinations": {loc.entity_id: derive_archive_path(loc.rel_path) for loc in locs},
        "applied": [],
        "skipped": [],
    }
    if not apply:
        return report

    index_path = archive_index_path(project_root)
    for loc in locs:
        original_bytes = loc.path.read_bytes()
        fm = dict(loc.frontmatter)
        fm["status"] = "archived"
        fm["consolidated_into"] = digest_id
        row = ArchiveRow(
            op="archive",
            id=loc.entity_id,
            kind=loc.kind,
            title=loc.title or None,
            aliases=[a for a in (loc.frontmatter.get("aliases") or []) if isinstance(a, str)],
            same_as=[s for s in (loc.frontmatter.get("same_as") or []) if isinstance(s, str)],
            status="archived",
            original_path=loc.rel_path,
            consolidated_into=digest_id,
            digest_insight=loc.title or None,
            reason="consolidated",
        )
        try:
            # Frontmatter rewrite + relocation share one guard: on ANY failure restore
            # the snapshotted bytes at the live path (move-rollback or un-executed move
            # leaves the file there) so a partial member is fully reverted.
            _atomic_replace_text(loc.path, _render_markdown(fm, loc.body))
            result = _relocate_rows(index_path, project_root, [row], now=now)
        except Exception:
            loc.path.write_bytes(original_bytes)
            raise
        report["applied"].extend(result["applied"])
        report["skipped"].extend(result["skipped"])
    return report

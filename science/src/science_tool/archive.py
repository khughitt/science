# science/src/science_tool/archive.py
"""Archive tier (P3): append-only index, relocation, and index-only resolution.

The active archive index — never archived-markdown scanning — is the source of
truth for archived-id resolution. Rows are append-only; reversal appends an
``unarchive`` tombstone. ``load_archive_index`` folds rows last-write-wins per id.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entity_scan import iter_entity_markdown

SCHEMA_VERSION = 1
ARCHIVE_SEGMENT = "_archive"
DEFAULT_ARCHIVE_STATUSES = frozenset({"superseded", "archived"})


class ArchiveRow(BaseModel):
    """One append-only operation. ``op`` discriminates archive vs unarchive; the
    P4-reserved fields (digest_insight/consolidated_into/cluster_id) are simply
    absent in P3 and read via ``.get``-style optional access."""
    schema_version: int = SCHEMA_VERSION
    op: str  # "archive" | "unarchive"
    id: str
    kind: str | None = None
    title: str | None = None
    aliases: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    status: str | None = None
    superseded_by: str | None = None
    original_path: str | None = None
    archived_at: str | None = None
    reason: str | None = None
    restored_path: str | None = None
    unarchived_at: str | None = None
    consolidated_into: str | None = None
    digest_insight: str | None = None


class ArchiveIndex(BaseModel):
    active_by_id: dict[str, ArchiveRow] = Field(default_factory=dict)

    def resolvable_ids(self) -> dict[str, str]:
        """alias/same_as/canonical -> canonical_id over ACTIVE entries only."""
        out: dict[str, str] = {}
        for canonical, row in self.active_by_id.items():
            out[canonical] = canonical
            for other in (*row.aliases, *row.same_as):
                out[other] = canonical
        return out


def archive_index_path(project_root: Path) -> Path:
    return project_root / "entities" / ARCHIVE_SEGMENT / "archive-index.jsonl"


def derive_archive_path(original_rel: str) -> str:
    """`entities/<rest>` -> `entities/_archive/<rest>` (kind subtree mirrored)."""
    parts = Path(original_rel).parts
    if not parts or parts[0] != "entities":
        raise ValueError(f"archive path must be under entities/: {original_rel!r}")
    return Path("entities", ARCHIVE_SEGMENT, *parts[1:]).as_posix()


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def append_row(index_path: Path, row: ArchiveRow) -> None:
    """Append one complete JSON line and fsync the index file + parent dir."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row.model_dump(), sort_keys=True) + "\n"
    with open(index_path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(index_path.parent)


def load_archive_index(project_root: Path) -> ArchiveIndex:
    """Fold rows last-write-wins per id; an id whose latest op is ``unarchive`` is
    dropped from the active set."""
    path = archive_index_path(project_root)
    active: dict[str, ArchiveRow] = {}
    if not path.is_file():
        return ArchiveIndex(active_by_id=active)
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        row = ArchiveRow.model_validate_json(raw)
        if row.op == "archive":
            active[row.id] = row
        elif row.op == "unarchive":
            active.pop(row.id, None)
    return ArchiveIndex(active_by_id=active)


class ArchiveError(Exception):
    """Raised on an unsafe archive/unarchive operation (fail-loud)."""


def _candidate_rows(project_root: Path, statuses: frozenset[str]) -> list[ArchiveRow]:
    """Live (non-archived) entities whose status is in ``statuses``, as archive rows."""
    rows: list[ArchiveRow] = []
    entities_root = project_root / "entities"
    for path in iter_entity_markdown(entities_root):  # archive skipped -> already-archived never re-seen
        fm = read_frontmatter(path)
        if not fm or "id" not in fm:
            continue
        status = fm.get("status")
        if status not in statuses:
            continue
        original_rel = path.relative_to(project_root).as_posix()
        rows.append(
            ArchiveRow(
                op="archive",
                id=str(fm["id"]),
                kind=fm.get("type") or fm.get("kind"),
                title=fm.get("title"),
                aliases=[a for a in (fm.get("aliases") or []) if isinstance(a, str)],
                same_as=[s for s in (fm.get("same_as") or []) if isinstance(s, str)],
                status=status,
                superseded_by=fm.get("superseded_by"),
                original_path=original_rel,
                reason=f"status:{status}",
            )
        )
    return sorted(rows, key=lambda r: r.id)


def _inbound_live_refs(project_root: Path, candidate_ids: set[str]) -> dict[str, list[str]]:
    """Map each candidate id -> sorted live entity ids that reference it via
    related: / source_refs: / relations[].target. Decision support: a survivor
    that still points at a to-be-archived entity shows up here (those refs stay
    resolvable post-archive via the index, but a human should see them)."""
    inbound: dict[str, set[str]] = {cid: set() for cid in candidate_ids}
    for path in iter_entity_markdown(project_root / "entities"):
        fm = read_frontmatter(path)
        if not fm or "id" not in fm:
            continue
        eid = str(fm["id"])
        if eid in candidate_ids:
            continue  # a candidate referencing another candidate is not a LIVE inbound ref
        refs: set[str] = set()
        for field in ("related", "source_refs"):
            refs.update(r for r in (fm.get(field) or []) if isinstance(r, str))
        for rel in fm.get("relations") or []:
            if isinstance(rel, dict) and isinstance(rel.get("target"), str):
                refs.add(rel["target"])
        for cid in refs & candidate_ids:
            inbound[cid].add(eid)
    return {cid: sorted(ids) for cid, ids in inbound.items()}


def _relocate_rows(
    index_path: Path,
    project_root: Path,
    rows: list[ArchiveRow],
    *,
    now: str | None,
) -> dict[str, list[str]]:
    """Content-agnostic relocation: move each row's file under _archive/ (move-first),
    append its index row, and roll the move back if the append fails. Performs NO
    frontmatter edits and owns no content snapshot — callers that mutate file content
    (e.g. consolidation) snapshot/restore around this call. Raises ArchiveError on a
    destination collision (never overwrites)."""
    applied: list[str] = []
    skipped: list[str] = []
    for row in rows:
        assert row.original_path is not None
        src = project_root / row.original_path
        dst = project_root / derive_archive_path(row.original_path)
        if not src.exists():
            skipped.append(row.id)
            continue
        if dst.exists():
            raise ArchiveError(
                f"cannot archive {row.id!r}: archive path {derive_archive_path(row.original_path)} "
                "already exists (run `science validate` to reconcile the archive index)"
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))  # move first
        _fsync_dir(dst.parent)
        try:
            append_row(index_path, row.model_copy(update={"archived_at": now}))
        except Exception:
            shutil.move(str(dst), str(src))  # roll back the move
            raise
        applied.append(row.id)
    return {"applied": applied, "skipped": skipped}


def archive_entities(
    project_root: Path,
    *,
    statuses: frozenset[str] = DEFAULT_ARCHIVE_STATUSES,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    """Report-then-apply relocation of hidden-status entities into the archive.
    Apply does move-first-then-append per entity, rolling the move back if the
    index append fails."""
    project_root = Path(project_root).resolve()
    rows = _candidate_rows(project_root, statuses)
    inbound = _inbound_live_refs(project_root, {r.id for r in rows})
    report: dict = {"candidates": [{"id": r.id, "kind": r.kind, "status": r.status,
                                    "original_path": r.original_path, "superseded_by": r.superseded_by,
                                    "inbound_live_refs": inbound.get(r.id, [])}
                                   for r in rows],
                    "applied": [], "skipped": []}
    if not apply:
        return report

    index_path = archive_index_path(project_root)
    result = _relocate_rows(index_path, project_root, rows, now=now)
    report["applied"] = result["applied"]
    report["skipped"] = result["skipped"]
    return report


def unarchive_entities(
    project_root: Path,
    ids: list[str],
    *,
    apply: bool = False,
    now: str | None = None,
) -> dict:
    """Restore archived entities to their original path; append unarchive tombstone.
    Collision (target exists) fails before moving — never overwrite."""
    project_root = Path(project_root).resolve()
    idx = load_archive_index(project_root)
    report: dict = {"candidates": [], "applied": [], "skipped": []}
    plans: list[tuple[ArchiveRow, Path, Path]] = []
    for eid in ids:
        row = idx.active_by_id.get(eid)
        if row is None:
            report["skipped"].append(eid)
            continue
        assert row.original_path is not None
        dst = project_root / row.original_path
        src = project_root / derive_archive_path(row.original_path)
        if dst.exists():
            raise ArchiveError(f"cannot unarchive {eid!r}: target {row.original_path} already exists")
        if not src.exists():
            raise ArchiveError(f"cannot unarchive {eid!r}: archived file missing at {src}")
        report["candidates"].append({"id": eid, "restored_path": row.original_path})
        plans.append((row, src, dst))
    if not apply:
        return report
    index_path = archive_index_path(project_root)
    for row, src, dst in plans:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        _fsync_dir(dst.parent)
        append_row(index_path, ArchiveRow(op="unarchive", id=row.id,
                                          restored_path=row.original_path, unarchived_at=now))
        report["applied"].append(row.id)
    return report


def search_archive(project_root: Path, query: str) -> list[dict]:
    """Case-insensitive substring search over active archive entries
    (id, title, kind, aliases, same_as). Returns sorted hit dicts."""
    q = query.lower()
    idx = load_archive_index(Path(project_root).resolve())
    hits: list[dict] = []
    for cid, row in idx.active_by_id.items():
        haystack = " ".join(filter(None, [cid, row.title or "", row.kind or "", *row.aliases, *row.same_as])).lower()
        if q in haystack:
            hits.append({"id": cid, "kind": row.kind, "title": row.title,
                         "status": row.status, "original_path": row.original_path})
    return sorted(hits, key=lambda h: h["id"])


def verify_archive(project_root: Path, live_alias_space: set[str]) -> list[str]:
    """Reconcile filesystem <-> active index and detect alias collisions against the
    caller-supplied live alias space. Returns a list of problem strings (empty ==
    clean). The caller builds ``live_alias_space`` from live entities (canonical ids
    + aliases + same_as); it must NOT be derived from ``sources.manual_aliases``,
    which load_project_sources augments with archive ids (that would make every
    archived id look like a self-collision). Project-authored manual-alias
    collisions are caught separately and fail loud at load time (see the
    load_project_sources merge in the graph task)."""
    project_root = Path(project_root).resolve()
    idx = load_archive_index(project_root)
    problems: list[str] = []

    # (a) every active row's file must exist at its derived archive path
    archived_present: set[str] = set()
    for eid, row in idx.active_by_id.items():
        assert row.original_path is not None
        dst = project_root / derive_archive_path(row.original_path)
        if dst.exists():
            archived_present.add(dst.resolve().as_posix())
        else:
            problems.append(f"active archive row {eid!r}: file missing at {derive_archive_path(row.original_path)}")

    # (b) every _archive/ markdown file must have an active row
    archive_root = project_root / "entities" / ARCHIVE_SEGMENT
    if archive_root.is_dir():
        for path in sorted(archive_root.rglob("*.md")):
            if path.resolve().as_posix() not in archived_present:
                rel = path.relative_to(project_root).as_posix()
                problems.append(f"archived file {rel} has no active index row")

    # (c) alias collisions — walk ACTIVE ROWS directly (NOT resolvable_ids(), which
    # already deduped tokens, hiding archive-vs-archive conflicts). Build
    # token -> set(owning canonical ids); >1 owner is an archive-vs-archive
    # collision; membership in live_alias_space is an archive-vs-live collision.
    owners: dict[str, set[str]] = {}
    for cid, row in idx.active_by_id.items():
        for token in (cid, *row.aliases, *row.same_as):
            owners.setdefault(token, set()).add(cid)
    for token, owning in sorted(owners.items()):
        if len(owning) > 1:
            problems.append(f"archive token {token!r} claimed by multiple active entries: {sorted(owning)}")
        if token in live_alias_space:
            problems.append(f"archive id/alias {token!r} collides with the live alias space")
    return problems

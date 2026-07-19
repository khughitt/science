from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from science_tool.archive import (
    ArchiveRow,
    _candidate_rows,
    _inbound_live_refs,
    _scope_rows_to_allowlist,
    archive_index_path,
    derive_archive_path,
)
from science_tool.plan_common import (
    ArchiveSelection,
    ArchiveStatusSweep,
    PathTransition,
    StateFingerprint,
    fingerprint,
)


class PlannedArchiveRow(ArchiveRow):
    # The canonical ArchiveRow tolerates unknown keys (it parses append-only index files that may
    # carry future fields); a frozen plan is untrusted, so tighten to extra="forbid" here.
    model_config = ConfigDict(extra="forbid")


class ArchiveCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str | None
    status: str | None
    original_path: str | None
    superseded_by: str | None
    resynthesized_into: list[str]
    inbound_live_refs: list[str]


class ArchivePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[ArchiveCandidate]


class ArchiveMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    original_path: str
    archive_path: str
    row: PlannedArchiveRow


class ArchivePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    project_root: str
    op: Literal["archive"]
    now: str
    selection: ArchiveSelection
    moves: list[ArchiveMove]
    index: PathTransition | None = None  # None for an empty cohort (a no-op plan; legacy archive no-ops too)
    transitions: list[PathTransition]
    preview_report: ArchivePreviewReport

    @model_validator(mode="after")
    def _index_matches_moves(self) -> ArchivePlan:
        # I5: the moves↔index relationship is a schema invariant, not just an apply-time check. A
        # non-empty cohort MUST carry an index; an empty cohort MUST carry neither an index nor any
        # transition. This makes a malformed plan unconstructable rather than merely refused later.
        if self.moves and self.index is None:
            raise ValueError("a non-empty cohort must carry an archive-index transition")
        if not self.moves and (self.index is not None or self.transitions):
            raise ValueError("an empty cohort must carry no index and no transitions")
        return self


_ABSENT = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)


def _fp_of_bytes(data: bytes, mode: int) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file",
                            content_sha256=hashlib.sha256(data).hexdigest(), mode=mode, symlink_target=None)


def _missing_ancestor_dirs(project_root: Path, dst_abs: Path, declared: set[Path]) -> list[Path]:
    """Every directory apply's `mkdir(parents=True)` would create for `dst_abs`, that does not yet
    exist and is not already declared — ordered OUTER→INNER so reverse-order rollback removes the
    innermost first. Finding 4: declaring only `dst.parent` leaves ancestors like `entities/_archive`
    with no transition or rollback state."""
    root = project_root.resolve()
    chain: list[Path] = []
    cur = dst_abs.parent
    while cur != root:
        chain.append(cur)  # inner first
        if root not in cur.parents:
            break  # safety: never walk above the project root
        cur = cur.parent
    chain.reverse()  # outer -> inner
    return [d for d in chain if not d.exists() and d not in declared]


def plan_archive(project_root: Path, *, selection: ArchiveSelection, now: str) -> ArchivePlan:
    project_root = Path(project_root).resolve()
    if isinstance(selection, ArchiveStatusSweep):
        statuses = frozenset(selection.statuses)
        rows = _candidate_rows(project_root, statuses)
    else:  # ExplicitArchiveIds
        statuses = frozenset(selection.allowed_statuses)
        rows = _scope_rows_to_allowlist(
            project_root, _candidate_rows(project_root, statuses), frozenset(selection.ids), statuses)
    inbound = _inbound_live_refs(project_root, {r.id for r in rows})

    moves: list[ArchiveMove] = []
    transitions: list[PathTransition] = []
    created_dirs: set[Path] = set()
    dir_post = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755,
                                symlink_target=None)
    for r in rows:
        assert r.original_path is not None
        frozen = PlannedArchiveRow(**r.model_copy(update={"archived_at": now}).model_dump())
        original = r.original_path
        archived = derive_archive_path(original)
        src_abs = project_root / original
        dst_abs = project_root / archived
        src_pre = fingerprint(src_abs)
        moves.append(ArchiveMove(id=r.id, original_path=original, archive_path=archived, row=frozen))
        # created-dir transitions FIRST (outer→inner), then src, then dst -- so reverse-order
        # rollback removes dst, restores src, then rmdir's inner→outer.
        for d in _missing_ancestor_dirs(project_root, dst_abs, created_dirs):
            created_dirs.add(d)
            transitions.append(PathTransition(role="created-dir",
                               rel_path=d.relative_to(project_root).as_posix(),
                               pre=_ABSENT, post=dir_post))
        transitions.append(PathTransition(role="archive-src", rel_path=original, pre=src_pre,
                                          post=_ABSENT))
        transitions.append(PathTransition(role="archive-dst", rel_path=archived, pre=_ABSENT,
                                          post=StateFingerprint(existed=True, type="file",
                                          content_sha256=src_pre.content_sha256, mode=src_pre.mode,
                                          symlink_target=None)))

    # Empty cohort → a no-op plan (no index transition), matching legacy `archive`'s no-op. Writing
    # an empty index into a possibly-absent `_archive/` would both create debris and diverge from legacy.
    index: PathTransition | None = None
    if moves:
        index_abs = archive_index_path(project_root)
        pre_bytes = index_abs.read_bytes() if index_abs.exists() else b""
        # EXACTLY append_row's serialization (json.dumps(model_dump, sort_keys=True) + "\n"), so the
        # frozen index round-trips through load_archive_index.
        appended = "".join(json.dumps(m.row.model_dump(), sort_keys=True) + "\n" for m in moves)
        post_bytes = pre_bytes + appended.encode("utf-8")
        index_pre = fingerprint(index_abs)
        index_mode = index_pre.mode if index_pre.existed else 0o644
        index = PathTransition(role="archive-index",
                               rel_path=index_abs.relative_to(project_root).as_posix(),
                               pre=index_pre, post=_fp_of_bytes(post_bytes, index_mode),
                               postimage=post_bytes.decode("utf-8"))

    report = ArchivePreviewReport(candidates=[
        ArchiveCandidate(id=r.id, kind=r.kind, status=r.status, original_path=r.original_path,
                         superseded_by=r.superseded_by, resynthesized_into=list(r.resynthesized_into),
                         inbound_live_refs=inbound.get(r.id, [])) for r in rows])
    return ArchivePlan(schema_version=1, project_root=str(project_root), op="archive", now=now,
                       selection=selection, moves=moves, index=index, transitions=transitions,
                       preview_report=report)

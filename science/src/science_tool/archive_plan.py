from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from science_tool.archive import (
    ArchiveError,
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
    PathEscape,
    PathTransition,
    StagingError,
    StateFingerprint,
    SurfaceMismatch,
    assert_same_surface,
    assert_staging_unique,
    fingerprint,
    matches,
    resolve_within,
    rollback_transitions,
    snapshot_paths,
    staged_write,
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
        if index_pre.existed:
            assert index_pre.mode is not None  # a present fingerprint always carries its exact mode
            index_mode = index_pre.mode
        else:
            index_mode = 0o644
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


_ARCHIVE_PLAN_SCHEMA = 1


class ArchiveApplyError(RuntimeError):
    pass


def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def apply_archive_plan(project_root: Path, plan: ArchivePlan, *, staging_token: str,
                       _fault: Callable[[str], None] | None = None) -> dict:
    """Replay a saved `ArchivePlan`: move each entity file with `os.rename` and append the
    archive-index atomically, rolling back on any failure.

    Gate order is load-bearing and MUST NOT be reordered (design/brief task-15):
      schema_version -> project_root -> Gate B (full re-derivation, FIRST) -> empty-cohort no-op
      -> structural -> pre-state -> execute (snapshot, mkdir declared dirs, os.rename moves,
      staged_write index, post-verify, rollback-on-failure).

    Unlike supersede, archive has NO Gate A digest -- Gate B's full re-derivation via `plan_archive`
    IS the primary drift gate, and it runs BEFORE the empty-cohort short-circuit so a corpus that
    gained an eligible entity since preview is caught as drift (I5), never reported as a silent
    successful no-op.
    """

    def fault(label: str) -> None:
        if _fault is not None:
            _fault(label)  # test-only kill seam; a BaseException here bypasses rollback

    project_root = project_root.resolve()
    if plan.schema_version != _ARCHIVE_PLAN_SCHEMA:
        raise ArchiveApplyError(
            f"unsupported plan schema_version {plan.schema_version} (this tool writes {_ARCHIVE_PLAN_SCHEMA})")
    if plan.project_root != str(project_root):
        raise ArchiveApplyError("plan project_root does not match")

    # Gate B FIRST -- re-derive the WHOLE plan from live sources and compare the complete surface.
    # Running this BEFORE the empty-cohort short-circuit means a corpus that gained an eligible
    # entity after preview is caught as drift, not silently reported as a successful no-op (I5).
    # `plan_archive` is read-only and derives its own paths from the live corpus, so it never
    # touches an untrusted plan path before containment is checked below.
    plan_index_list = [plan.index] if plan.index is not None else []
    try:
        expected = plan_archive(project_root, selection=plan.selection, now=plan.now)
    except ArchiveError as exc:
        raise ArchiveApplyError(f"corpus changed since preview: {exc}") from exc
    if expected.moves != plan.moves or expected.index != plan.index:
        raise ArchiveApplyError("re-derived moves/rows/index differ from the plan (corpus changed since preview)")
    exp_index = [expected.index] if expected.index is not None else []
    try:
        assert_same_surface([*plan.transitions, *plan_index_list], [*expected.transitions, *exp_index])
    except SurfaceMismatch as exc:
        raise ArchiveApplyError(f"declared transitions differ from re-derived: {exc}") from exc
    if expected.preview_report != plan.preview_report:
        raise ArchiveApplyError("re-derived preview report differs from the plan")

    # Empty cohort -- a no-op plan writes nothing (legacy `archive_entities` no-ops too). Only
    # reachable once Gate B has confirmed the live corpus ALSO derives an empty cohort.
    if not plan.moves:
        if plan.index is not None or plan.transitions:
            raise ArchiveApplyError("empty cohort must carry no index or transitions")
        return {"applied": [], "skipped": []}

    index_list = plan_index_list
    all_t = [*plan.transitions, *index_list]
    # Structural -- containment for every declared path, canonical archive paths, staging
    # uniqueness, no duplicate move ids.
    try:
        abs_by_t = {id(t): resolve_within(project_root, t.rel_path) for t in all_t}
        for m in plan.moves:
            resolve_within(project_root, m.original_path)
            resolve_within(project_root, m.archive_path)
        if plan.index is not None:
            assert_staging_unique(project_root, [abs_by_t[id(plan.index)]], staging_token)
    except (PathEscape, StagingError) as exc:
        raise ArchiveApplyError(str(exc)) from exc
    for m in plan.moves:
        if derive_archive_path(m.original_path) != m.archive_path:
            raise ArchiveApplyError(f"non-canonical archive_path for {m.id}")
    ids = [m.id for m in plan.moves]
    if len(ids) != len(set(ids)):
        raise ArchiveApplyError("duplicate move ids")

    # Pre-state gate -- do NOT write until every declared path's live state matches its frozen pre.
    for t in all_t:
        if not matches(t.pre, abs_by_t[id(t)]):
            raise ArchiveApplyError(f"pre-state changed for {t.rel_path}")

    # Execute -- snapshot every declared path, create declared dirs, rename each move (never
    # os.replace -- a move must fail loud, not silently clobber), stage+commit the index, verify
    # post-state, roll back atomically on any failure.
    snap = snapshot_paths([abs_by_t[id(t)] for t in all_t])
    try:
        for t in plan.transitions:
            if t.role == "created-dir":
                d = abs_by_t[id(t)]
                d.mkdir(parents=False, exist_ok=True)  # every ancestor is its own transition
                assert t.post.mode is not None  # post.existed=True dir fingerprint always carries a mode
                os.chmod(d, t.post.mode)
        for m in plan.moves:
            src = project_root / m.original_path
            dst = project_root / m.archive_path
            try:
                os.rename(src, dst)  # NOT os.replace -- a move must refuse rather than clobber
            except OSError as exc:
                if exc.errno == errno.EXDEV:
                    raise ArchiveApplyError(
                        f"cross-device move refused for {m.id}: archive must be same filesystem") from exc
                raise
            _fsync_dir(src.parent)
            _fsync_dir(dst.parent)
            fault(f"renamed:{m.id}")  # kill boundary: after each rename, before the index write
        if plan.index is not None:
            assert plan.index.postimage is not None  # archive-index role always carries a postimage
            assert plan.index.post.mode is not None  # post.existed=True fingerprint always carries a mode
            staged_write(abs_by_t[id(plan.index)], plan.index.postimage,
                         plan.index.post.mode, staging_token,
                         target_pre=plan.index.pre)  # mode concrete; target_pre guards cleanup
            fault("index-written")  # kill boundary: after index replacement
        for t in all_t:
            if not matches(t.post, abs_by_t[id(t)]):
                raise ArchiveApplyError(f"post-state verification failed for {t.rel_path}")
    except Exception as exc:
        rollback_transitions(all_t, project_root, snap)  # may raise RollbackHalt (propagates)
        if isinstance(exc, ArchiveApplyError):
            raise
        raise ArchiveApplyError(f"archive apply failed and rolled back: {exc}") from exc
    return {"applied": [m.id for m in plan.moves], "skipped": []}

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_entities, archive_index_path
from science_tool.plan_common import (
    ArchiveStatusSweep, ExplicitArchiveIds, PathTransition, StateFingerprint, fingerprint, staging_path_for,
)
from science_tool.archive_plan import (
    ArchiveApplyError, ArchiveCandidate, ArchiveMove, ArchivePlan, ArchivePreviewReport, PlannedArchiveRow,
    apply_archive_plan, plan_archive,
)


def _fp_file(sha: str) -> StateFingerprint:
    return StateFingerprint(existed=True, type="file", content_sha256=sha, mode=0o644, symlink_target=None)


def test_archive_plan_roundtrips_and_forbids_extra() -> None:
    # A VALID empty plan (moves=[], index=None, transitions=[]) round-trips through JSON. The
    # moves↔index invariant means this is the only coherent empty shape.
    plan = ArchivePlan(
        schema_version=1, project_root="/p", op="archive", now="2026-07-18T00:00:00Z",
        selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
        moves=[], index=None, transitions=[],
        preview_report=ArchivePreviewReport(candidates=[]),
    )
    assert ArchivePlan.model_validate_json(plan.model_dump_json()) == plan


def test_archive_plan_rejects_incoherent_moves_index_shapes() -> None:
    # I5: the _index_matches_moves validator rejects both incoherent shapes at construction time.
    import hashlib
    body = "index bytes\n"
    idx = PathTransition(role="archive-index", rel_path="entities/_archive/archive-index.jsonl",
                         pre=StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None),
                         post=_fp_file(hashlib.sha256(body.encode()).hexdigest()), postimage=body)
    common = dict(schema_version=1, project_root="/p", op="archive", now="2026-07-18T00:00:00Z",
                  selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                  preview_report=ArchivePreviewReport(candidates=[]))
    with pytest.raises(ValueError, match="empty cohort"):
        ArchivePlan(**common, moves=[], index=idx, transitions=[])  # empty cohort with an index
    a_move = ArchiveMove(id="interpretation:0001-x", original_path="entities/interpretations/0001-x.md",
                         archive_path="entities/_archive/interpretations/0001-x.md",
                         row=PlannedArchiveRow(op="archive", id="interpretation:0001-x"))
    with pytest.raises(ValueError, match="non-empty cohort"):
        ArchivePlan(**common, moves=[a_move], index=None, transitions=[])  # moves but no index


def test_nested_archive_models_forbid_extra_keys() -> None:
    with pytest.raises(ValueError):
        ArchivePreviewReport(candidates=[], bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        ArchiveCandidate(id="x:1", kind="k", status="superseded", original_path="p",
                         superseded_by=None, resynthesized_into=[], inbound_live_refs=[],
                         bogus=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        PlannedArchiveRow(op="archive", id="x:1", unknown_future_key="v")  # type: ignore[call-arg]


def test_base_archive_row_tolerates_unknown_key() -> None:
    # The base ArchiveRow (extra="ignore" by default) tolerates unknown keys that future versions
    # may add, whereas PlannedArchiveRow (extra="forbid") rejects them. This test demonstrates
    # the differential: base accepts and silently drops the unknown key.
    row = ArchiveRow(op="archive", id="x:1", unknown_future_key="v")  # type: ignore[call-arg]
    assert "unknown_future_key" not in row.model_dump()


def test_planned_row_is_a_valid_archive_row() -> None:
    # PlannedArchiveRow IS an ArchiveRow (subclass), so a frozen row is guaranteed row-shaped.
    from science_tool.archive import ArchiveRow
    row = PlannedArchiveRow(op="archive", id="interpretation:0001-x", archived_at="2026-07-18T00:00:00Z")
    assert isinstance(row, ArchiveRow)


def _superseded(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: X\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")


def _oracle_append_bytes(rows: list[ArchiveRow], scratch_dir: Path, *, prior_bytes: bytes = b"") -> bytes:
    """The ORACLE for what `plan_archive` should freeze as its index postimage: the REAL
    `append_row` (archive.py:84-92), called once per row against a scratch index file that starts
    from `prior_bytes` (empty for a fresh index, or real prior content for the append branch).
    If append_row's serialization ever diverges from plan_archive's literal, this helper's output
    diverges too."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    index_path = scratch_dir / "oracle-index.jsonl"
    if prior_bytes:
        index_path.write_bytes(prior_bytes)
    for row in rows:
        append_row(index_path, row)
    return index_path.read_bytes()


def test_plan_archive_freezes_move_and_literal_index(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    assert len(plan.moves) == 1
    m = plan.moves[0]
    assert m.id == "interpretation:0001-x"
    assert m.original_path == "entities/interpretations/0001-x.md"
    assert m.archive_path == "entities/_archive/interpretations/0001-x.md"
    assert m.row.archived_at == "2026-07-18T00:00:00Z"  # a typed PlannedArchiveRow, not a dict
    assert plan.index.role == "archive-index"
    assert plan.index.postimage.endswith("\n")
    assert "interpretation:0001-x" in plan.index.postimage
    # a src transition exists with the live pre-state
    src = [t for t in plan.transitions if t.role == "archive-src"][0]
    assert src.pre == fingerprint(tmp_path / src.rel_path)


def test_index_postimage_matches_canonical_append_row_serialization(tmp_path: Path) -> None:
    # ORACLE check: `expected` comes from the REAL append_row (archive.py:84-92) writing to a
    # real file on disk, NOT from re-deriving plan_archive's own json.dumps(...)+"\n" formula. If
    # append_row's serialization ever drifts from plan_archive's literal, this test must fail.
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    oracle_bytes = _oracle_append_bytes([m.row for m in plan.moves], tmp_path / "_oracle")
    assert plan.index.postimage.encode("utf-8") == oracle_bytes


def test_plan_archive_appends_onto_a_real_prior_index(tmp_path: Path) -> None:
    # Covers the pre-existing-index APPEND branch: `pre_bytes = index.read_bytes()` when the index
    # already exists and is non-empty, not the `else b""` arm every other test exercises.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: X\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-y.md").write_text(
        "---\nid: interpretation:0002-y\nkind: interpretation\ntitle: Y\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")

    # Batch 1: really archive 0001-x via the production op (apply=True), seeding a REAL prior
    # archive-index.jsonl -- not a hand-written fixture.
    first = archive_entities(
        tmp_path, statuses=frozenset({"superseded"}), ids=frozenset({"interpretation:0001-x"}),
        apply=True, now="2026-07-18T00:00:00Z")
    assert first["applied"] == ["interpretation:0001-x"]
    prior_bytes = archive_index_path(tmp_path).read_bytes()
    assert prior_bytes != b""  # the non-empty pre_bytes arm this test exists to exercise

    # Batch 2: plan_archive for the second (still-live) candidate must prepend the REAL prior bytes.
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T01:00:00Z")
    assert len(plan.moves) == 1
    assert plan.moves[0].id == "interpretation:0002-y"
    postimage_bytes = plan.index.postimage.encode("utf-8")
    assert postimage_bytes.startswith(prior_bytes)
    assert len(postimage_bytes) > len(prior_bytes)

    # Oracle: appending the plan's own row onto the real prior index via the REAL append_row
    # reproduces the frozen literal byte-for-byte.
    oracle_bytes = _oracle_append_bytes(
        [m.row for m in plan.moves], tmp_path / "_oracle2", prior_bytes=prior_bytes)
    assert postimage_bytes == oracle_bytes


def test_plan_archive_declares_every_missing_ancestor_dir(tmp_path: Path) -> None:
    # Finding 4: apply does mkdir(parents=True); every ancestor it would create must be declared,
    # or rollback has no state for the undeclared ones.
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    created = sorted(t.rel_path for t in plan.transitions if t.role == "created-dir")
    assert created == ["entities/_archive", "entities/_archive/interpretations"]


def test_plan_archive_empty_cohort_is_a_noop_plan(tmp_path: Path) -> None:
    # No superseded entities → no moves, no transitions, and NO index transition (legacy no-op).
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    (tmp_path / "entities" / "interpretations").mkdir(parents=True)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    assert plan.moves == []
    assert plan.transitions == []
    assert plan.index is None
    assert plan.preview_report.candidates == []


class _Kill(BaseException):
    """Simulates an uncaught process kill — NOT an Exception, so apply's rollback never runs."""


def test_apply_archive_plan_moves_entity_and_writes_index(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    report = apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert report["applied"] == ["interpretation:0001-x"]
    assert not (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()
    idx = (tmp_path / "entities" / "_archive" / "archive-index.jsonl").read_text(encoding="utf-8")
    assert "interpretation:0001-x" in idx
    assert idx == plan.index.postimage
    from science_tool.archive import load_archive_index
    assert "interpretation:0001-x" in load_archive_index(tmp_path).active_by_id


def test_apply_archive_empty_cohort_is_a_noop(tmp_path: Path) -> None:
    # No candidates → apply writes nothing and never touches a (possibly-absent) _archive/.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    (tmp_path / "entities" / "interpretations").mkdir(parents=True)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    report = apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert report == {"applied": [], "skipped": []}
    assert not (tmp_path / "entities" / "_archive").exists()  # no debris


def test_apply_empty_cohort_refuses_when_corpus_gained_an_eligible_entity(tmp_path: Path) -> None:
    # I5: an empty saved plan must still pass Gate B. If the corpus gained an eligible entity between
    # preview and apply, the re-derivation is non-empty ≠ the empty plan → refused as drift, NOT a
    # silent successful no-op.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    assert plan.moves == []
    # a new superseded entity appears after preview
    (d / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: X\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")
    with pytest.raises(ArchiveApplyError, match="differ from the plan|corpus changed"):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_explicit_ids_wraps_gate_b_archive_error_as_archive_apply_error(tmp_path: Path) -> None:
    # Finding (whole-branch review): for an EXPLICIT-IDS plan, if an allowlisted entity is deleted
    # or changes status between preview and apply, Gate B's re-derivation calls plan_archive ->
    # _scope_rows_to_allowlist, which raises a raw ArchiveError. apply_archive_plan must wrap that
    # as ArchiveApplyError (the SUPERSEDE sibling does the analogous wrap for SupersessionError),
    # not let the raw ArchiveError escape as an uncaught traceback.
    _superseded(tmp_path)
    plan = plan_archive(
        tmp_path,
        selection=ExplicitArchiveIds(kind="explicit_ids", ids=["interpretation:0001-x"],
                                     allowed_statuses=["superseded"]),
        now="2026-07-18T00:00:00Z")
    assert plan.moves and plan.moves[0].id == "interpretation:0001-x"

    # Between preview and apply, the allowlisted entity is deleted outright, so re-derivation's
    # `_scope_rows_to_allowlist` finds it unresolved and raises a raw ArchiveError ("not found").
    (tmp_path / "entities" / "interpretations" / "0001-x.md").unlink()

    with pytest.raises(ArchiveApplyError, match="corpus changed since preview"):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_refuses_cross_device_move_loudly(tmp_path: Path, monkeypatch) -> None:
    # I8 / design §4.3: a cross-device rename raises EXDEV; apply must surface it as a clean refusal
    # (archive must be on the same filesystem), not a partial/ambiguous move.
    import errno
    import os
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")

    def exdev(src, dst):
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "rename", exdev)
    with pytest.raises(ArchiveApplyError, match="cross-device"):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    # rolled back: the source is still in place, nothing half-moved
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()


def test_apply_archive_refuses_when_source_changed_after_preview(tmp_path: Path) -> None:
    # design §9 (drift rejection — src changed): mutating the source after preview is refused (the
    # re-derived row/pre-state no longer matches the plan).
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    (tmp_path / "entities" / "interpretations" / "0001-x.md").write_text(
        "---\nid: interpretation:0001-x\nkind: interpretation\ntitle: CHANGED\nstatus: superseded\n---\nbody\n",
        encoding="utf-8")
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # not moved


def test_apply_archive_refuses_project_root_mismatch(tmp_path: Path) -> None:
    # design §9 (drift rejection — project mismatch).
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    other = plan.model_copy(update={"project_root": str(tmp_path / "nope")})
    with pytest.raises(ArchiveApplyError, match="project_root"):
        apply_archive_plan(tmp_path, other, staging_token="tok")


def test_apply_archive_refuses_when_index_changed_after_preview(tmp_path: Path) -> None:
    # design §9 (drift rejection — INDEX changed), ISOLATED from created-dir drift: `_archive/` exists
    # BEFORE preview, so `plan_archive` emits no created-dir transition for it and the transition surface
    # is identical at preview and apply (`_archive/interpretations/` stays absent throughout — it is
    # never touched here). The ONLY thing that diverges afterward is the index file, so a failure is
    # specifically the index guard: re-derivation reads the new bytes and produces a different index
    # postimage/pre, and Gate B refuses rather than clobber a concurrently-written index. Source stays put.
    _superseded(tmp_path)
    (tmp_path / "entities" / "_archive").mkdir(parents=True)  # created-dir surface fixed BEFORE preview
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    index_abs.write_text('{"id":"interpretation:9999-z"}\n', encoding="utf-8")  # ONLY the index diverges
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # not moved


def test_apply_archive_refuses_when_destination_appeared_after_preview(tmp_path: Path) -> None:
    # design §9 (drift rejection — DST appeared), ISOLATED from created-dir drift: the destination's
    # PARENT exists BEFORE preview, so `plan_archive` emits NO created-dir transitions (both `_archive/`
    # and `_archive/interpretations/` already exist) and the transition surface is identical at preview
    # and apply. The ONLY change afterward is the destination FILE appearing, so a failure is specifically
    # the dst guard: `plan_archive` freezes archive-dst with `pre=_ABSENT`, and the pre-state gate
    # (`matches(pre=absent, live=exists)` is False) refuses BEFORE any rename, leaving both untouched.
    _superseded(tmp_path)
    dst = tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md"
    dst.parent.mkdir(parents=True)  # created-dir surface fixed BEFORE preview
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    dst.write_text("SOMETHING ALREADY HERE", encoding="utf-8")  # ONLY the destination file appears
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # src not moved
    assert dst.read_text(encoding="utf-8") == "SOMETHING ALREADY HERE"          # dst untouched


def test_apply_archive_refuses_report_hiding_an_inbound_reference(tmp_path: Path) -> None:
    # I8 / design §9 "Report binding": a plan whose preview_report omits a live inbound reference to
    # an archived entity is refused at Gate B (the re-derived report carries the inbound ref).
    _superseded(tmp_path)
    # a live entity references the to-be-archived 0001-x
    (tmp_path / "entities" / "interpretations" / "0009-live.md").write_text(
        "---\nid: interpretation:0009-live\nkind: interpretation\ntitle: L\nstatus: active\n"
        "relations:\n  - predicate: sci:relatedTo\n    target: interpretation:0001-x\n---\nbody\n",
        encoding="utf-8")
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    cand = plan.preview_report.candidates[0]
    assert "interpretation:0009-live" in cand.inbound_live_refs  # preview surfaced it
    hidden = cand.model_copy(update={"inbound_live_refs": []})
    tampered = plan.model_copy(update={
        "preview_report": plan.preview_report.model_copy(update={"candidates": [hidden]})})
    with pytest.raises(ArchiveApplyError, match="preview report"):
        apply_archive_plan(tmp_path, tampered, staging_token="tok")


def test_apply_archive_refuses_unsupported_schema_version(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    plan = plan.model_copy(update={"schema_version": 999})
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_refuses_tampered_row(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    bad = plan.moves[0].row.model_copy(update={"title": "TAMPERED"})
    plan.moves[0] = plan.moves[0].model_copy(update={"row": bad})
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_refuses_absolute_rel_path_escape(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    src = [t for t in plan.transitions if t.role == "archive-src"][0]
    idx = plan.transitions.index(src)
    plan.transitions[idx] = src.model_copy(update={"rel_path": "/etc/evil.md"})
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")


def test_apply_archive_rolls_back_when_index_write_is_blocked(tmp_path: Path) -> None:
    # Move-rollback: a stale, non-prefix staging survivor makes the index write fail AFTER the entity
    # moved. The StagingError is wrapped as ArchiveApplyError only after rollback returns the corpus
    # to its pre-state — src restored, dst removed.
    _superseded(tmp_path)
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    index_abs.parent.mkdir(parents=True, exist_ok=True)  # so the parent exists before planning
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    staging_path_for(index_abs, "tok").write_text("garbage-not-a-prefix", encoding="utf-8")
    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok")
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # src restored
    assert not (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()  # dst gone


def test_kill_after_rename_leaves_a_classifiable_declared_state(tmp_path: Path) -> None:
    # Kill matrix — after each archive rename: src moved away, dst present, index NOT yet written.
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")

    def fault(label: str) -> None:
        if label == "renamed:interpretation:0001-x":
            raise _Kill()

    with pytest.raises(_Kill):
        apply_archive_plan(tmp_path, plan, staging_token="tok", _fault=fault)
    assert not (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()
    assert not (tmp_path / "entities" / "_archive" / "archive-index.jsonl").exists()  # index == pre (absent)


def test_kill_after_index_replacement_leaves_complete_index_no_survivor(tmp_path: Path) -> None:
    # Kill matrix — after index replacement: index is complete, no staging survivor left behind.
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")

    def fault(label: str) -> None:
        if label == "index-written":
            raise _Kill()

    with pytest.raises(_Kill):
        apply_archive_plan(tmp_path, plan, staging_token="tok", _fault=fault)
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    assert index_abs.read_text(encoding="utf-8") == plan.index.postimage  # complete
    assert not staging_path_for(index_abs, "tok").exists()  # no undeclared debris


def test_apply_archive_index_leaves_no_staging_survivor(tmp_path: Path) -> None:
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    apply_archive_plan(tmp_path, plan, staging_token="tok")
    index_abs = tmp_path / "entities" / "_archive" / "archive-index.jsonl"
    assert not staging_path_for(index_abs, "tok").exists()

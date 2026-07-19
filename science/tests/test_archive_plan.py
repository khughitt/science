from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import ArchiveRow
from science_tool.plan_common import ArchiveStatusSweep, PathTransition, StateFingerprint, fingerprint
from science_tool.archive_plan import (
    ArchiveCandidate, ArchiveMove, ArchivePlan, ArchivePreviewReport, PlannedArchiveRow, plan_archive,
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
    # The frozen index bytes must be exactly what append_row would have written, or the index
    # will not round-trip through load_archive_index.
    import json
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status", statuses=["superseded"]),
                        now="2026-07-18T00:00:00Z")
    expected = json.dumps(plan.moves[0].row.model_dump(), sort_keys=True) + "\n"
    assert plan.index.postimage == expected


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

from __future__ import annotations

import pytest

from science_tool.archive import ArchiveRow
from science_tool.plan_common import ArchiveStatusSweep, PathTransition, StateFingerprint
from science_tool.archive_plan import (
    ArchiveCandidate, ArchiveMove, ArchivePlan, ArchivePreviewReport, PlannedArchiveRow,
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

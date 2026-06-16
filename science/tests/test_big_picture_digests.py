# tests/test_big_picture_digests.py
from __future__ import annotations

import dataclasses as dc

from science_tool.big_picture.digests import (
    ClusterDigest,
    MemberSummary,
    redirect_refs,
)


def test_redirect_refs_rewrites_mapped_and_passes_through() -> None:
    remap = {"interpretation:i01-old": "synthesis:d1", "old-alias": "synthesis:d1"}
    out = redirect_refs(
        ["question:q1", "interpretation:i01-old", "old-alias", "hypothesis:h1"],
        remap,
    )
    # i01-old and old-alias both collapse to synthesis:d1, de-duped, order kept.
    assert out == ["question:q1", "synthesis:d1", "hypothesis:h1"]


def test_redirect_refs_identity_on_empty_remap_still_dedups() -> None:
    assert redirect_refs(["a", "b", "a", "c"], {}) == ["a", "b", "c"]


def test_dataclasses_are_frozen_with_defaults() -> None:
    cd = ClusterDigest(id="synthesis:d1", title="T")
    ms = MemberSummary(id="x", kind="finding", title="t", digest_insight="i", archived=True)
    assert dc.is_dataclass(cd) and cd.__dataclass_params__.frozen
    assert dc.is_dataclass(ms) and ms.__dataclass_params__.frozen
    assert cd.member_count == 0 and cd.members == [] and cd.member_ids == [] and cd.related == []


from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.big_picture.digests import member_to_digest


def test_member_to_digest_built_from_index_with_aliases(tmp_path) -> None:
    idx = archive_index_path(tmp_path)
    append_row(idx, ArchiveRow(
        op="archive", id="interpretation:i01-old", kind="interpretation",
        title="Old", aliases=["i01-alias"], same_as=["interpretation:i01-sameas"],
        status="archived", consolidated_into="synthesis:d1", archived_at="T1"))
    append_row(idx, ArchiveRow(
        op="archive", id="interpretation:i02-old", kind="interpretation",
        status="archived", consolidated_into="synthesis:d1", archived_at="T1"))
    assert member_to_digest(tmp_path) == {
        "interpretation:i01-old": "synthesis:d1",
        "i01-alias": "synthesis:d1",
        "interpretation:i01-sameas": "synthesis:d1",
        "interpretation:i02-old": "synthesis:d1",
    }


def test_member_to_digest_excludes_plain_archives(tmp_path) -> None:
    # A plain P3 archive (no consolidated_into) must NOT appear in the map.
    append_row(archive_index_path(tmp_path), ArchiveRow(
        op="archive", id="finding:f1", kind="finding", status="archived", archived_at="T1"))
    assert member_to_digest(tmp_path) == {}


def test_member_to_digest_empty_when_no_index(tmp_path) -> None:
    assert member_to_digest(tmp_path) == {}

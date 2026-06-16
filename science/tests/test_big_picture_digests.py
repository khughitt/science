# tests/test_big_picture_digests.py
from __future__ import annotations

import dataclasses as dc

import pytest

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.big_picture.digests import (
    ClusterDigest,
    MemberSummary,
    load_cluster_digests,
    member_to_digest,
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


def test_member_to_digest_raises_on_key_mapping_to_two_digests(tmp_path) -> None:
    # An alias of one archived row collides with a different row's canonical id,
    # but the two rows consolidated into DIFFERENT digests -> integrity violation.
    idx = archive_index_path(tmp_path)
    append_row(idx, ArchiveRow(
        op="archive", id="interpretation:i01", kind="interpretation",
        status="archived", consolidated_into="synthesis:d1", archived_at="T1"))
    append_row(idx, ArchiveRow(
        op="archive", id="interpretation:i02", kind="interpretation",
        aliases=["interpretation:i01"], status="archived",
        consolidated_into="synthesis:d2", archived_at="T1"))
    with pytest.raises(ValueError, match="two digests"):
        member_to_digest(tmp_path)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_cluster_digests_default_ignores_non_digest_synthesis(tmp_path) -> None:
    syn = tmp_path / "entities" / "synthesis"
    _write(syn / "0001-d.md",
        '---\nid: "synthesis:0001-d"\ntitle: "Partition digest"\n'
        'report_kind: "cluster-digest"\nstatus: "active"\n'
        'related: ["question:q01", "hypothesis:h01"]\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n'
        '  - predicate: "sci:consolidates"\n    target: "interpretation:i02-old"\n---\nbody\n')
    _write(syn / "0002-roll.md",
        '---\nid: "synthesis:0002-roll"\nreport_kind: "synthesis-rollup"\nstatus: "active"\n---\nx\n')

    digests = load_cluster_digests(tmp_path)
    assert set(digests) == {"synthesis:0001-d"}
    d = digests["synthesis:0001-d"]
    assert d.title == "Partition digest"
    assert d.related == ["question:q01", "hypothesis:h01"]
    assert d.member_ids == ["interpretation:i01-old", "interpretation:i02-old"]
    assert d.member_count == 2
    assert d.members == []  # default is not deep


def test_load_cluster_digests_deep_pulls_index_only_summaries(tmp_path) -> None:
    syn = tmp_path / "entities" / "synthesis"
    _write(syn / "0001-d.md",
        '---\nid: "synthesis:0001-d"\ntitle: "D"\nreport_kind: "cluster-digest"\nstatus: "active"\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n'
        '  - predicate: "sci:consolidates"\n    target: "interpretation:i02-old"\n---\nx\n')
    append_row(archive_index_path(tmp_path), ArchiveRow(
        op="archive", id="interpretation:i01-old", kind="interpretation",
        title="Old i01", status="archived", consolidated_into="synthesis:0001-d",
        digest_insight="i01 says X", archived_at="T1"))

    d = load_cluster_digests(tmp_path, deep=True)["synthesis:0001-d"]
    # i01 is archived+indexed; i02 absent (e.g. not yet applied) -> archived=False.
    assert [(m.id, m.archived, m.digest_insight) for m in d.members] == [
        ("interpretation:i01-old", True, "i01 says X"),
        ("interpretation:i02-old", False, None),
    ]


def test_load_cluster_digests_empty_without_synthesis_dir(tmp_path) -> None:
    assert load_cluster_digests(tmp_path) == {}

# tests/test_cluster_digests_cli.py
from __future__ import annotations

import json

from click.testing import CliRunner

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.cli import main


def _project(tmp_path):
    syn = tmp_path / "entities" / "synthesis"
    syn.mkdir(parents=True)
    (syn / "0001-d.md").write_text(
        '---\nid: "synthesis:0001-d"\ntitle: "Partition digest"\n'
        'report_kind: "cluster-digest"\nstatus: "active"\n'
        'related: ["question:q01", "hypothesis:h01"]\n'
        'relations:\n  - predicate: "sci:consolidates"\n    target: "interpretation:i01-old"\n'
        '  - predicate: "sci:consolidates"\n    target: "interpretation:i02-old"\n---\nbody\n',
        encoding="utf-8")
    append_row(archive_index_path(tmp_path), ArchiveRow(
        op="archive", id="interpretation:i01-old", kind="interpretation", title="Old i01",
        aliases=["i01-alias"], status="archived", consolidated_into="synthesis:0001-d",
        digest_insight="i01 says X", archived_at="T1"))
    return tmp_path


def test_cluster_digests_group_lists_subcommand() -> None:
    result = CliRunner().invoke(main, ["big-picture", "--help"])
    assert result.exit_code == 0
    assert "cluster-digests" in result.output


def test_cluster_digests_default_contract(tmp_path) -> None:
    root = _project(tmp_path)
    result = CliRunner().invoke(main, ["big-picture", "cluster-digests", "--project-root", str(root)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) == {"digests", "member_to_digest"}
    d = payload["digests"]["synthesis:0001-d"]
    assert d["member_count"] == 2
    assert d["member_ids"] == ["interpretation:i01-old", "interpretation:i02-old"]
    assert d["members"] == []  # default: not deep
    assert payload["member_to_digest"] == {
        "interpretation:i01-old": "synthesis:0001-d",
        "i01-alias": "synthesis:0001-d",
    }


def test_cluster_digests_deep_attaches_member_summaries(tmp_path) -> None:
    root = _project(tmp_path)
    result = CliRunner().invoke(
        main, ["big-picture", "cluster-digests", "--project-root", str(root), "--deep"])
    assert result.exit_code == 0, result.output
    members = json.loads(result.output)["digests"]["synthesis:0001-d"]["members"]
    by_id = {m["id"]: m for m in members}
    assert by_id["interpretation:i01-old"]["archived"] is True
    assert by_id["interpretation:i01-old"]["digest_insight"] == "i01 says X"
    assert by_id["interpretation:i02-old"]["archived"] is False

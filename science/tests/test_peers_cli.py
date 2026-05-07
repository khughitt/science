"""Tests for science-tool peers CLI."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _write_yaml(path: Path, body: str) -> None:
    (path / "science.yaml").write_text(body, encoding="utf-8")


def test_peers_list_table(tmp_path: Path) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: peer
id: peer
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host)])
    assert result.exit_code == 0, result.output
    assert "peer" in result.output
    assert "ok" in result.output


def test_peers_list_json(tmp_path: Path) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: peer
id: peer
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["project_id"] == "host"
    assert len(payload["peers"]) == 1
    assert payload["peers"][0] == {
        "id": "peer",
        "path": str(peer),
        "resolved": str(peer.resolve()),
        "status": "ok",
        "issues": [],
    }


def test_peers_list_path_missing(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "path-missing" in result.output


def test_peers_list_error_status_wins_over_warning_with_issue_details(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
    git: https://github.com/example/ghost
""",
    )
    runner = CliRunner()

    table_result = runner.invoke(main, ["peers", "list", "--project-root", str(host)])
    assert table_result.exit_code == 0, table_result.output
    assert "reserved-field" in table_result.output

    json_result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert json_result.exit_code == 0, json_result.output
    row = json.loads(json_result.output)["peers"][0]
    assert row["status"] == "reserved-field"
    assert row["resolved"] is None
    assert [issue["kind"] for issue in row["issues"]] == [
        "reserved_field",
        "path_missing",
    ]
    assert {issue["severity"] for issue in row["issues"]} == {"error", "warning"}
    assert all(issue["detail"] for issue in row["issues"])


def test_peers_list_self_peer_status_precedes_reserved_field(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: host
    path: {host}
    git: https://github.com/example/host
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    row = json.loads(result.output)["peers"][0]

    assert row["status"] == "self-peer"
    assert [issue["kind"] for issue in row["issues"][:2]] == [
        "self_peer",
        "reserved_field",
    ]


def test_peers_list_reserved_field_order_matches_validator(
    tmp_path: Path,
) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: peer
id: peer
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
    zeta: unsupported
    git: https://github.com/example/peer
    alpha: unsupported
    doi: 10.0000/example
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    details = [issue["detail"] for issue in json.loads(result.output)["peers"][0]["issues"]]

    assert details == [
        "unknown peer field 'alpha' is not supported",
        "reserved peer field 'doi' is not yet supported",
        "reserved peer field 'git' is not yet supported",
        "unknown peer field 'zeta' is not supported",
    ]


def test_peers_list_duplicate_peer_id_status_wins_over_path_missing(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: ../missing-a
  - id: dup
    path: ../missing-b
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [row["status"] for row in payload["peers"]] == [
        "duplicate-peer-id",
        "duplicate-peer-id",
    ]
    assert {issue["kind"] for row in payload["peers"] for issue in row["issues"]} >= {
        "duplicate_peer_id",
        "path_missing",
    }


def test_peers_list_three_duplicate_rows_deduplicates_global_duplicate_issue(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: ../missing-a
  - id: dup
    path: ../missing-b
  - id: dup
    path: ../missing-c
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["peers"]

    for row in rows:
        assert [issue["kind"] for issue in row["issues"]].count("duplicate_peer_id") == 1


def test_peers_list_mixed_duplicate_paths_keep_row_local_resolved(
    tmp_path: Path,
) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: dup
id: dup
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {peer}
  - id: dup
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["peers"]

    assert rows[0]["resolved"] == str(peer.resolve())
    assert rows[0]["status"] == "duplicate-peer-id"
    assert "path_missing" not in {issue["kind"] for issue in rows[0]["issues"]}

    assert rows[1]["resolved"] is None
    assert rows[1]["status"] == "duplicate-peer-id"
    assert {issue["kind"] for issue in rows[1]["issues"]} >= {
        "duplicate_peer_id",
        "path_missing",
    }


def test_peers_list_duplicate_id_mismatch_stays_on_matching_row(
    tmp_path: Path,
) -> None:
    good = tmp_path / "good"
    good.mkdir()
    _write_yaml(
        good,
        """
name: good
id: dup
profile: research
research_question: "..."
""",
    )
    mismatch = tmp_path / "mismatch"
    mismatch.mkdir()
    _write_yaml(
        mismatch,
        """
name: mismatch
id: actual
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {good}
  - id: dup
    path: {mismatch}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["peers"]

    assert "id_mismatch" not in {issue["kind"] for issue in rows[0]["issues"]}
    assert "id_mismatch" in {issue["kind"] for issue in rows[1]["issues"]}


def test_peers_list_duplicate_local_graph_missing_stays_on_matching_row(
    tmp_path: Path,
) -> None:
    good = tmp_path / "good"
    good.mkdir()
    _write_yaml(
        good,
        """
name: good
id: dup
profile: research
research_question: "..."
""",
    )
    missing_graph = tmp_path / "missing-graph"
    missing_graph.mkdir()
    _write_yaml(
        missing_graph,
        """
name: missing-graph
id: dup
profile: research
research_question: "..."
""",
    )
    (missing_graph / "knowledge").mkdir()
    (missing_graph / "knowledge" / "composite.trig").write_text("# minimal\n", encoding="utf-8")
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {good}
  - id: dup
    path: {missing_graph}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["peers"]

    assert "local_graph_missing" not in {issue["kind"] for issue in rows[0]["issues"]}
    assert "local_graph_missing" in {issue["kind"] for issue in rows[1]["issues"]}


def test_peers_list_no_peers(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "no peers declared" in result.output.lower()


def test_peers_show(tmp_path: Path) -> None:
    peer = tmp_path / "mm30-dir"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: multiple-myeloma-30
id: mm30
role: cancer-type
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: mm30
    path: {peer}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "show", "mm30", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "declared_id: mm30" in result.output
    assert "project_id:  mm30" in result.output
    assert "multiple-myeloma-30" in result.output
    assert "cancer-type" in result.output


def test_peers_show_duplicate_peer_id_fails_cleanly(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.mkdir()
    _write_yaml(
        first,
        """
name: first
id: dup
profile: research
research_question: "..."
""",
    )
    second = tmp_path / "second"
    second.mkdir()
    _write_yaml(
        second,
        """
name: second
id: dup
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {first}
  - id: dup
    path: {second}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "show", "dup", "--project-root", str(host)])
    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit)
    assert "error:" in result.output.lower()
    assert "duplicate peer id" in result.output.lower()
    assert "dup" in result.output


def test_peers_show_unresolved_peer_fails_with_context(tmp_path: Path) -> None:
    peer = tmp_path / "peer-without-config"
    peer.mkdir()
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: broken
    path: {peer}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "show", "broken", "--project-root", str(host)])
    assert result.exit_code != 0
    assert "broken" in result.output
    assert "no science.yaml" in result.output.lower()


def test_peers_show_unknown_fails(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "show", "ghost", "--project-root", str(host)])
    assert result.exit_code != 0
    assert "ghost" in result.output.lower()


def test_peers_check_clean(tmp_path: Path) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(peer, 'name: peer\nid: peer\nprofile: research\nresearch_question: "..."\n')
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "ok" in result.output.lower()


def test_peers_check_warning_does_not_fail(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "path_missing" in result.output or "path-missing" in result.output


def test_peers_check_does_not_require_full_project_config_validation(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
role: standalone
children:
  - id: unrelated
    path: ../unrelated
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host)])
    assert result.exit_code == 0, result.output
    assert "path_missing" in result.output
    assert "1 peers" in result.output


def test_peers_check_warning_json_outputs_issue_fields(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host), "--format=json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert set(payload[0]) == {"kind", "peer_id", "detail", "severity"}
    assert payload[0]["kind"] == "path_missing"
    assert payload[0]["peer_id"] == "ghost"
    assert payload[0]["severity"] == "warning"
    assert "../missing" in payload[0]["detail"]


def test_peers_check_error_exits_nonzero(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(exist_ok=True)
    _write_yaml(a, 'name: a\nid: dup\nprofile: research\nresearch_question: "..."\n')
    b.mkdir(exist_ok=True)
    _write_yaml(b, 'name: b\nid: dup\nprofile: research\nresearch_question: "..."\n')
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {a}
  - id: dup
    path: {b}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host)])
    assert result.exit_code != 0
    assert "ok:" not in result.output
    assert "failed:" in result.output


def test_peers_check_error_json_outputs_issue_before_nonzero(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(exist_ok=True)
    _write_yaml(a, 'name: a\nid: dup\nprofile: research\nresearch_question: "..."\n')
    b.mkdir(exist_ok=True)
    _write_yaml(b, 'name: b\nid: dup\nprofile: research\nresearch_question: "..."\n')
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {a}
  - id: dup
    path: {b}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host), "--format=json"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert any(
        issue["kind"] == "duplicate_peer_id" and issue["peer_id"] == "dup" and issue["severity"] == "error"
        for issue in payload
    )


def test_peers_check_strict_treats_warnings_as_errors(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host), "--strict"])
    assert result.exit_code != 0
    assert "ok:" not in result.output
    assert "failed:" in result.output


def test_peers_check_strict_warning_json_outputs_issue_before_nonzero(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["peers", "check", "--project-root", str(host), "--format=json", "--strict"],
    )
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload[0]["kind"] == "path_missing"
    assert payload[0]["peer_id"] == "ghost"
    assert payload[0]["severity"] == "warning"

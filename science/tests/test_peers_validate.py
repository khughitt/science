"""Tests for science_tool.peers_validate."""

from __future__ import annotations

from pathlib import Path


def _write_minimal_science_yaml(root: Path, project_id: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        f"""
name: {project_id}
id: {project_id}
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )


def test_no_peers_returns_empty(tmp_path: Path) -> None:
    from science_tool.peers_validate import validate_peers

    root = tmp_path / "host"
    _write_minimal_science_yaml(root, "host")
    assert validate_peers(root) == []


def test_path_missing_warning(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
        encoding="utf-8",
    )

    issues = validate_peers(root)

    assert len(issues) == 1
    assert issues[0].kind is PeerIssueKind.PATH_MISSING
    assert issues[0].peer_id == "ghost"
    assert issues[0].severity == "warning"


def test_not_a_project_warning(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    junk = tmp_path / "junk"
    junk.mkdir()
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: junk
    path: {junk}
""",
        encoding="utf-8",
    )

    issues = validate_peers(root)

    assert len(issues) == 1
    assert issues[0].kind is PeerIssueKind.NOT_A_PROJECT
    assert issues[0].severity == "warning"


def test_id_mismatch_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    peer = tmp_path / "peer-dir"
    _write_minimal_science_yaml(peer, "actual-id")
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: declared-id
    path: {peer}
""",
        encoding="utf-8",
    )

    issues = validate_peers(root)

    assert any(issue.kind is PeerIssueKind.ID_MISMATCH for issue in issues)
    mismatch = next(issue for issue in issues if issue.kind is PeerIssueKind.ID_MISMATCH)
    assert mismatch.severity == "error"
    assert "actual-id" in mismatch.detail
    assert "declared-id" in mismatch.detail


def test_duplicate_peer_id_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    a = tmp_path / "a"
    b = tmp_path / "b"
    _write_minimal_science_yaml(a, "dup")
    _write_minimal_science_yaml(b, "dup")
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
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
        encoding="utf-8",
    )

    issues = validate_peers(root)

    assert any(issue.kind is PeerIssueKind.DUPLICATE_PEER_ID for issue in issues)
    dup = next(issue for issue in issues if issue.kind is PeerIssueKind.DUPLICATE_PEER_ID)
    assert dup.severity == "error"


def test_self_peer_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: host
    path: {root}
""",
        encoding="utf-8",
    )

    issues = validate_peers(root)

    assert any(issue.kind is PeerIssueKind.SELF_PEER for issue in issues)


def test_reserved_field_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    peer = tmp_path / "peer"
    _write_minimal_science_yaml(peer, "peer")
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
    git: https://github.com/example/peer
""",
        encoding="utf-8",
    )

    issues = validate_peers(root)

    assert any(issue.kind is PeerIssueKind.RESERVED_FIELD and "git" in issue.detail for issue in issues)


def test_reserved_field_issues_are_sorted_by_field_name(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    peer = tmp_path / "peer"
    _write_minimal_science_yaml(peer, "peer")
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
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
        encoding="utf-8",
    )

    reserved_issues = [issue for issue in validate_peers(root) if issue.kind is PeerIssueKind.RESERVED_FIELD]

    assert [issue.detail for issue in reserved_issues] == [
        "unknown peer field 'alpha' is not supported",
        "reserved peer field 'doi' is not yet supported",
        "reserved peer field 'git' is not yet supported",
        "unknown peer field 'zeta' is not supported",
    ]


def test_local_graph_missing_warning(tmp_path: Path) -> None:
    """Peer has composite.trig but no graph.trig: surfaced as warning."""
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    peer = tmp_path / "peer"
    _write_minimal_science_yaml(peer, "peer")
    (peer / "knowledge").mkdir()
    (peer / "knowledge" / "composite.trig").write_text("# minimal\n", encoding="utf-8")

    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
        encoding="utf-8",
    )

    issues = validate_peers(root)

    assert any(issue.kind is PeerIssueKind.LOCAL_GRAPH_MISSING for issue in issues)

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import importlib
import pytest

from science_tool.peers_validate import PeerIssueKind
from science_tool.validate import Result, Severity, ValidateContext


def _write_manifest(root: Path, *, peers: str = "") -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "id: demo",
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
                peers,
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path, *, verbose: bool = False, peers: str = "") -> ValidateContext:
    _write_manifest(root, peers=peers)
    return ValidateContext.from_project_root(root, strict=False, verbose=verbose)


def _messages(results: list[Result], severity: Severity | None = None) -> list[str]:
    return [result.message for result in results if severity is None or result.severity is severity]


def test_peer_valid_empty_audit_no_graph_stops_before_graph_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.validate.checks import graph

    def fail_call(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("graph.trig-gated API should not be called")

    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root: ([], False))
    monkeypatch.setattr(graph, "validate_graph", fail_call)
    monkeypatch.setattr(graph, "diff_graph_inputs", fail_call)
    monkeypatch.setattr(graph, "list_inquiries", fail_call)
    monkeypatch.setattr(graph, "validate_inquiry", fail_call)

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert [(result.severity, result.message) for result in results] == [
        (Severity.INFO, "peer check: declared peers valid"),
        (Severity.INFO, "graph audit: all canonical references resolved"),
    ]


def test_peer_errors_emit_all_cli_lines_and_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    issues = [
        SimpleNamespace(
            severity="warning",
            peer_id="other",
            kind=PeerIssueKind.LOCAL_GRAPH_MISSING,
            detail="missing knowledge/graph.trig",
        ),
        SimpleNamespace(
            severity="error",
            peer_id="demo",
            kind=PeerIssueKind.SELF_PEER,
            detail="project 'demo' lists itself as a peer",
        ),
    ]
    monkeypatch.setattr(graph, "validate_peers", lambda _root: issues)
    monkeypatch.setattr(graph, "materialization_audit", lambda _root: ([], False))

    results = list(
        graph.check_graph(
            _ctx(
                tmp_path,
                peers="\n".join(
                    [
                        "peers:",
                        "  - id: other",
                        "    path: ../other",
                        "  - id: demo",
                        "    path: .",
                    ]
                ),
            )
        )
    )

    assert _messages(results, Severity.ERROR) == [
        "peer check failed: WARNING [other] local_graph_missing: missing knowledge/graph.trig",
        "peer check failed: ERROR [demo] self_peer: project 'demo' lists itself as a peer",
        "peer check failed: failed: 2 peers, 1 warning, 1 error",
    ]


def test_graph_audit_rows_map_fail_to_error_and_others_to_warn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(
        graph,
        "materialization_audit",
        lambda _root: (
            [
                {
                    "check": "broken_ref",
                    "status": "fail",
                    "source": "doc/a.md",
                    "field": "related",
                    "target": "paper:x",
                    "details": "missing",
                },
                {
                    "check": "soft_ref",
                    "status": "warn",
                    "source": "doc/b.md",
                    "field": "tags",
                    "target": "concept:y",
                    "details": "weak",
                },
            ],
            True,
        ),
    )

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert _messages(results, Severity.ERROR) == ["graph audit: broken_ref — doc/a.md related -> paper:x (missing)"]
    assert _messages(results, Severity.WARN) == ["graph audit: soft_ref — doc/b.md tags -> concept:y (weak)"]


def test_graph_validate_rows_map_statuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root: ([], False))
    monkeypatch.setattr(
        graph,
        "validate_graph",
        lambda _path: (
            [
                {"check": "parseable", "status": "pass", "details": "ok"},
                {"check": "orphaned", "status": "warn", "details": "1 orphan"},
                {"check": "acyclic", "status": "fail", "details": "cycle"},
            ],
            True,
        ),
    )
    monkeypatch.setattr(graph, "diff_graph_inputs", lambda **_kwargs: [])
    monkeypatch.setattr(graph, "list_inquiries", lambda _path: [])

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert "graph validate: acyclic — cycle" in _messages(results, Severity.ERROR)
    assert "graph validate: orphaned — 1 orphan" in _messages(results, Severity.WARN)
    assert "graph validate: parseable — ok" in _messages(results, Severity.INFO)


def test_diff_rows_emit_stale_warning_and_verbose_details(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root: ([], False))
    monkeypatch.setattr(graph, "validate_graph", lambda _path: ([], False))
    monkeypatch.setattr(
        graph,
        "diff_graph_inputs",
        lambda **_kwargs: [
            {"path": "doc/a.md", "reason": "hash_changed"},
            {"path": "notes/b.md", "reason": "new_file"},
        ],
    )
    monkeypatch.setattr(graph, "list_inquiries", lambda _path: [])

    results = list(graph.check_graph(_ctx(tmp_path, verbose=True)))

    assert "graph has 2 stale input file(s) — run /science:update-graph" in _messages(results, Severity.WARN)
    assert "  doc/a.md (hash_changed)" in _messages(results, Severity.INFO)
    assert "  notes/b.md (new_file)" in _messages(results, Severity.INFO)


def test_inquiry_validation_maps_statuses_and_verbose_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root: ([], False))
    monkeypatch.setattr(graph, "validate_graph", lambda _path: ([], False))
    monkeypatch.setattr(graph, "diff_graph_inputs", lambda **_kwargs: [])
    monkeypatch.setattr(graph, "list_inquiries", lambda _path: [{"slug": "demo"}])
    monkeypatch.setattr(
        graph,
        "validate_inquiry",
        lambda _path, _slug: [
            {"check": "shape", "status": "pass", "message": "ok"},
            {"check": "scope", "status": "warn", "message": "loose"},
            {"check": "boundary", "status": "fail", "message": "broken"},
        ],
    )

    non_verbose_results = list(graph.check_graph(_ctx(tmp_path)))
    verbose_results = list(graph.check_graph(_ctx(tmp_path, verbose=True)))

    assert "inquiry 'demo': boundary — broken" in _messages(non_verbose_results, Severity.ERROR)
    assert "inquiry 'demo': scope — loose" in _messages(non_verbose_results, Severity.WARN)
    assert "inquiry 'demo': shape — ok" not in _messages(non_verbose_results, Severity.INFO)
    assert "Checking inquiries (1)..." in _messages(verbose_results, Severity.INFO)
    assert "inquiry 'demo': shape — ok" in _messages(verbose_results, Severity.INFO)


def test_registry_loads_graph_after_notes_at_order_17() -> None:
    from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests
    import science_tool.validate.checks.graph as graph
    import science_tool.validate.checks.notes as notes

    clear_checks_for_tests()
    try:
        importlib.reload(notes)
        importlib.reload(graph)

        sections = [entry.section for entry in CANONICAL_CHECKS]
        graph_index = sections.index("knowledge graph...")

        assert sections[graph_index - 1] == "notes..."
        assert CANONICAL_CHECKS[graph_index].order == 17
    finally:
        clear_checks_for_tests()

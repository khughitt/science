from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from science_tool.instruments import InstrumentResult, ValidationVerdict
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
    return [result.message for result in results if severity is None or result.severity == severity.value]


def test_peer_valid_empty_audit_no_graph_stops_before_graph_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.validate.checks import graph

    def fail_call(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("graph.trig-gated API should not be called")

    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "validate_graph", fail_call)
    monkeypatch.setattr(ValidateContext, "graph_dataset", fail_call)
    monkeypatch.setattr(graph, "validate_graph_dataset", fail_call)
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", fail_call)
    monkeypatch.setattr(graph, "list_inquiries_dataset", fail_call)
    monkeypatch.setattr(graph, "validate_inquiry_dataset", fail_call)

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert [(result.severity, result.message) for result in results] == [
        (Severity.INFO, "peer check: declared peers valid"),
        (Severity.INFO, "graph audit: all canonical references resolved"),
    ]


def test_validate_check_audit_side_unwired_emits_error(tmp_path, monkeypatch) -> None:
    from science_tool.validate.checks import graph

    monkeypatch.setattr(
        graph,
        "materialization_audit",
        lambda _root, **_kwargs: ValidationVerdict.unwired(code="unparseable", reason="boom"),
    )
    results = list(graph.check_graph(_ctx(tmp_path)))
    errors = [
        r
        for r in results
        if r.severity == Severity.ERROR and "graph audit: could not run (unparseable): boom" in r.message
    ]
    assert errors, "expected an ERROR finding for the unwired audit"
    assert not any("all canonical references resolved" in r.message for r in results)


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
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))

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
        lambda _root, **_kwargs: ValidationVerdict.from_has_failures(
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
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(
        graph,
        "validate_graph_dataset",
        lambda _dataset: ValidationVerdict.failed(
            [
                {"check": "parseable", "status": "pass", "details": "ok"},
                {"check": "orphaned", "status": "warn", "details": "1 orphan"},
                {"check": "acyclic", "status": "fail", "details": "cycle"},
            ]
        ),
    )
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda _dataset, **_kwargs: InstrumentResult[dict].empty())
    monkeypatch.setattr(graph, "list_inquiries_dataset", lambda _dataset: InstrumentResult[dict].empty())

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert "graph validate: acyclic — cycle" in _messages(results, Severity.ERROR)
    assert "graph validate: orphaned — 1 orphan" in _messages(results, Severity.WARN)
    assert "graph validate: parseable — ok" in _messages(results, Severity.INFO)


def test_graph_validate_skip_status_is_info_not_a_crash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A `skip` row must not abort the section.

    `causal_acyclicity` emits `skip` whenever a project has no scic:causes edges
    (graph/store/validation.py). Rejecting it here raised ValueError out of
    check_graph, so every later graph check stopped running and the whole section
    was reported as one `validate.check-error`.
    """
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(
        graph,
        "validate_graph_dataset",
        lambda _dataset: ValidationVerdict.passed(
            [
                {
                    "check": "causal_acyclicity",
                    "status": "skip",
                    "details": "no scic:causes edges in the project — nothing to check for cycles",
                },
                {"check": "parseable", "status": "pass", "details": "ok"},
            ]
        ),
    )
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda _dataset, **_kwargs: InstrumentResult[dict].empty())
    monkeypatch.setattr(graph, "list_inquiries_dataset", lambda _dataset: InstrumentResult[dict].empty())

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert (
        "graph validate: causal_acyclicity — no scic:causes edges in the project — nothing to check for cycles"
        in _messages(results, Severity.INFO)
    )
    assert _messages(results, Severity.ERROR) == []
    # The rows after the skip still ran.
    assert "graph validate: parseable — ok" in _messages(results, Severity.INFO)


def test_validate_check_unwired_emits_error_and_skips_diff(tmp_path, monkeypatch) -> None:
    from science_tool.instruments import ValidationVerdict
    from science_tool.validate.checks import graph

    called = {"diff": False}
    monkeypatch.setattr(
        graph,
        "validate_graph",
        lambda _p: ValidationVerdict.unwired(code="unparseable", reason="bad"),
    )
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))

    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda *a, **k: called.__setitem__("diff", True))
    # force the except branch: make ctx.graph_dataset raise (a broken graph.trig on disk)
    gdir = tmp_path / "knowledge"
    gdir.mkdir()
    (gdir / "graph.trig").write_text("not trig <<<", encoding="utf-8")

    results = list(graph.check_graph(_ctx(tmp_path)))
    msgs = [r.message for r in results if "graph validate" in r.message]
    assert any("could not run (unparseable): bad" in m for m in msgs)
    assert called["diff"] is False


def test_graph_validate_fallback_renders_rows_and_skips_dataset_followups(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("not trig <<<", encoding="utf-8")

    def fail_load(_ctx: ValidateContext, _path: Path) -> None:
        raise ValueError("dataset unavailable")

    def fail_followup(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dataset follow-up should not be called after fallback validation")

    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(ValidateContext, "graph_dataset", fail_load)
    monkeypatch.setattr(
        graph,
        "validate_graph",
        lambda _path: ValidationVerdict.passed([{"check": "parseable", "status": "pass", "details": "fallback ok"}]),
    )
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", fail_followup)
    monkeypatch.setattr(graph, "list_inquiries_dataset", fail_followup)
    monkeypatch.setattr(graph, "validate_inquiry_dataset", fail_followup)

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert "graph validate: parseable — fallback ok" in _messages(results, Severity.INFO)


def test_graph_check_reuses_one_loaded_dataset_for_graph_followups(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    loaded_dataset = object()
    load_calls: list[Path] = []
    validated_inquiries: list[tuple[object, str]] = []

    def load_dataset(path: Path) -> object:
        load_calls.append(path)
        return loaded_dataset

    def fail_path_api(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("path-based graph API should not be called by validate.checks.graph")

    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(ValidateContext, "graph_dataset", lambda _ctx, path: load_dataset(path))
    monkeypatch.setattr(
        graph,
        "validate_graph_dataset",
        lambda dataset: ValidationVerdict.passed([{"check": "parseable_trig", "status": "pass", "details": "ok"}]),
        raising=False,
    )
    monkeypatch.setattr(
        graph,
        "diff_graph_inputs_dataset",
        lambda dataset, *, graph_path, mode: InstrumentResult[dict].empty(),
        raising=False,
    )
    monkeypatch.setattr(
        graph,
        "list_inquiries_dataset",
        lambda dataset: InstrumentResult.from_rows([{"slug": "one"}, {"slug": "two"}]),
        raising=False,
    )

    def validate_inquiry_dataset(dataset: object, slug: str) -> InstrumentResult[dict[str, str]]:
        validated_inquiries.append((dataset, slug))
        return InstrumentResult.from_rows([{"check": "shape", "status": "pass", "message": "ok"}])

    monkeypatch.setattr(graph, "validate_inquiry_dataset", validate_inquiry_dataset, raising=False)
    monkeypatch.setattr(graph, "validate_graph", fail_path_api)
    monkeypatch.setattr(graph, "diff_graph_inputs", fail_path_api, raising=False)
    monkeypatch.setattr(graph, "list_inquiries", fail_path_api, raising=False)
    monkeypatch.setattr(graph, "validate_inquiry", fail_path_api, raising=False)

    results = list(graph.check_graph(_ctx(tmp_path, verbose=True)))

    assert load_calls == [graph_path]
    assert validated_inquiries == [(loaded_dataset, "one"), (loaded_dataset, "two")]
    assert "Checking inquiries (2)..." in _messages(results, Severity.INFO)


def test_parseable_trig_failure_stops_graph_followups(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("not trig", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(
        graph,
        "validate_graph",
        lambda _path: ValidationVerdict.unwired(
            code="unparseable",
            reason="graph.trig did not parse: bad syntax",
        ),
    )

    def fail_call(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("graph follow-up API should not be called after parse failure")

    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", fail_call)
    monkeypatch.setattr(graph, "list_inquiries_dataset", fail_call)
    monkeypatch.setattr(graph, "validate_inquiry_dataset", fail_call)

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert "graph validate: could not run (unparseable): graph.trig did not parse: bad syntax" in _messages(
        results, Severity.ERROR
    )


def test_graph_audit_unknown_status_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(
        graph,
        "materialization_audit",
        lambda _root, **_kwargs: ValidationVerdict.from_has_failures(
            [
                {
                    "check": "broken_ref",
                    "status": "mystery",
                    "source": "doc/a.md",
                    "field": "related",
                    "target": "paper:x",
                    "details": "missing",
                }
            ],
            False,
        ),
    )

    with pytest.raises(ValueError, match="graph audit returned unknown status: mystery"):
        list(graph.check_graph(_ctx(tmp_path)))


def test_graph_validate_unknown_status_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(
        graph,
        "validate_graph_dataset",
        lambda _dataset: ValidationVerdict.passed([{"check": "parseable", "status": "mystery", "details": "ok"}]),
    )

    with pytest.raises(ValueError, match="graph validate returned unknown status: mystery"):
        list(graph.check_graph(_ctx(tmp_path)))


def test_diff_rows_emit_stale_warning_and_verbose_details(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ValidationVerdict.passed([]))
    monkeypatch.setattr(
        graph,
        "diff_graph_inputs_dataset",
        lambda _dataset, **_kwargs: InstrumentResult.from_rows(
            [
                {"path": "doc/a.md", "status": "stale", "reason": "hash_changed"},
                {"path": "notes/b.md", "status": "stale", "reason": "new_file"},
            ]
        ),
    )
    monkeypatch.setattr(graph, "list_inquiries_dataset", lambda _dataset: InstrumentResult[dict].empty())

    results = list(graph.check_graph(_ctx(tmp_path, verbose=True)))

    assert "graph has 2 stale input file(s) — run /science:update-graph" in _messages(results, Severity.WARN)
    assert "  doc/a.md (hash_changed)" in _messages(results, Severity.INFO)
    assert "  notes/b.md (new_file)" in _messages(results, Severity.INFO)


def test_diff_unknown_status_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ValidationVerdict.passed([]))
    monkeypatch.setattr(
        graph,
        "diff_graph_inputs_dataset",
        lambda _dataset, **_kwargs: InstrumentResult.from_rows(
            [{"path": "doc/a.md", "status": "fresh", "reason": "ok"}]
        ),
    )

    with pytest.raises(ValueError, match="graph diff returned unknown status: fresh"):
        list(graph.check_graph(_ctx(tmp_path)))


def test_inquiry_validation_maps_statuses_and_verbose_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda _dataset, **_kwargs: InstrumentResult[dict].empty())
    monkeypatch.setattr(
        graph, "list_inquiries_dataset", lambda _dataset: InstrumentResult.from_rows([{"slug": "demo"}])
    )
    monkeypatch.setattr(
        graph,
        "validate_inquiry_dataset",
        lambda _dataset, _slug: InstrumentResult.from_rows(
            [
                {"check": "shape", "status": "pass", "message": "ok"},
                {"check": "causal_optional", "status": "skip", "message": "not causal"},
                {"check": "causal_note", "status": "info", "message": "informational"},
                {"check": "scope", "status": "warn", "message": "loose"},
                {"check": "boundary", "status": "fail", "message": "broken"},
            ]
        ),
    )

    non_verbose_results = list(graph.check_graph(_ctx(tmp_path)))
    verbose_results = list(graph.check_graph(_ctx(tmp_path, verbose=True)))

    assert "inquiry 'demo': boundary — broken" in _messages(non_verbose_results, Severity.ERROR)
    assert "inquiry 'demo': scope — loose" in _messages(non_verbose_results, Severity.WARN)
    assert "inquiry 'demo': shape — ok" not in _messages(non_verbose_results, Severity.INFO)
    assert "inquiry 'demo': causal_optional — not causal" not in _messages(non_verbose_results, Severity.INFO)
    assert "inquiry 'demo': causal_note — informational" not in _messages(non_verbose_results, Severity.INFO)
    assert "Checking inquiries (1)..." in _messages(verbose_results, Severity.INFO)
    assert "inquiry 'demo': shape — ok" in _messages(verbose_results, Severity.INFO)
    assert "inquiry 'demo': causal_optional — not causal" in _messages(verbose_results, Severity.INFO)
    assert "inquiry 'demo': causal_note — informational" in _messages(verbose_results, Severity.INFO)


def test_inquiry_no_inquiry_block_is_info_but_missing_subgraph_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A thin doc-authored inquiry (no_inquiry_block) surfaces as INFO, not WARN;
    a patch-definition whose subgraph is missing (no_inquiry_subgraph) stays WARN
    (fb-2026-07-11-030)."""
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda _dataset, **_kwargs: InstrumentResult[dict].empty())
    monkeypatch.setattr(
        graph,
        "list_inquiries_dataset",
        lambda _dataset: InstrumentResult.from_rows([{"slug": "thin"}, {"slug": "broken"}]),
    )

    def validate(_dataset: object, slug: str) -> InstrumentResult[dict[str, str]]:
        if slug == "thin":
            return InstrumentResult.unwired(code="no_inquiry_block", reason="thin doc-authored")
        return InstrumentResult.unwired(code="no_inquiry_subgraph", reason="expected but missing")

    monkeypatch.setattr(graph, "validate_inquiry_dataset", validate)

    results = list(graph.check_graph(_ctx(tmp_path)))

    assert "inquiry 'thin': structural checks did not run (no_inquiry_block)" in _messages(results, Severity.INFO)
    assert "inquiry 'thin': structural checks did not run (no_inquiry_block)" not in _messages(results, Severity.WARN)
    assert "inquiry 'broken': structural checks did not run (no_inquiry_subgraph)" in _messages(results, Severity.WARN)


def test_inquiry_value_error_propagates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda _dataset, **_kwargs: InstrumentResult[dict].empty())
    monkeypatch.setattr(
        graph, "list_inquiries_dataset", lambda _dataset: InstrumentResult.from_rows([{"slug": "demo"}])
    )

    def raise_value_error(_dataset: object, _slug: str) -> list[dict[str, str]]:
        raise ValueError("inquiry graph is malformed")

    monkeypatch.setattr(graph, "validate_inquiry_dataset", raise_value_error)

    with pytest.raises(ValueError, match="inquiry graph is malformed"):
        list(graph.check_graph(_ctx(tmp_path)))


def test_inquiry_unknown_status_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    graph_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(graph, "validate_peers", lambda _root: [])
    monkeypatch.setattr(graph, "materialization_audit", lambda _root, **_kwargs: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "validate_graph_dataset", lambda _dataset: ValidationVerdict.passed([]))
    monkeypatch.setattr(graph, "diff_graph_inputs_dataset", lambda _dataset, **_kwargs: InstrumentResult[dict].empty())
    monkeypatch.setattr(
        graph, "list_inquiries_dataset", lambda _dataset: InstrumentResult.from_rows([{"slug": "demo"}])
    )
    monkeypatch.setattr(
        graph,
        "validate_inquiry_dataset",
        lambda _dataset, _slug: InstrumentResult.from_rows([{"check": "shape", "status": "mystery", "message": "ok"}]),
    )

    with pytest.raises(ValueError, match="inquiry validate returned unknown status: mystery"):
        list(graph.check_graph(_ctx(tmp_path)))


def _write_duplicate_markdown_owners(root: Path) -> None:
    # Two markdown files declaring the SAME id -> two owner rows -> an identity
    # collision in the compiled table. Pre-2b-Task-3, check_graph surfaced it as a
    # `graph audit: identity_collision ...` ERROR; now the dedicated
    # forbidden-second-declaration check owns that diagnostic, so check_graph must
    # not emit it.
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    for fname in ("x.md", "x-dup.md"):
        (d / fname).write_text(
            '---\nid: "dataset:x"\nkind: "dataset"\ntitle: "x"\n'
            'origin: "external"\n'
            'access:\n  level: "public"\n  verified: false\n---\n',
            encoding="utf-8",
        )


def test_check_graph_does_not_emit_identity_collision(tmp_path: Path) -> None:
    from science_tool.validate.checks import graph

    ctx = _ctx(tmp_path)
    _write_duplicate_markdown_owners(tmp_path)
    messages = _messages(list(graph.check_graph(ctx)))
    assert not any("identity_collision" in m for m in messages)


def test_registry_loads_graph_after_notes_at_order_17() -> None:
    import science_tool.validate.checks.graph as graph
    import science_tool.validate.checks.notes as notes
    from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests

    clear_checks_for_tests()
    try:
        importlib.reload(notes)
        importlib.reload(graph)

        sections = [entry.section for entry in CANONICAL_CHECKS]
        graph_index = sections.index("graph")

        assert sections[graph_index - 1] == "notes"
        assert CANONICAL_CHECKS[graph_index].order == 17
    finally:
        clear_checks_for_tests()

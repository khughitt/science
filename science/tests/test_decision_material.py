from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

from science_tool.consolidation import (
    _project_inputs, _SUPERSEDES, build_decision_material, build_supersedes_graph,
    build_supersedes_graph_from_material, decision_digest, load_supersession_inputs,
)


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8",
    )
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n"
        "superseded_by: interpretation:0001-a\n---\nbody\n",
        encoding="utf-8",
    )


def test_decision_digest_is_stable_across_runs(tmp_path: Path) -> None:
    _seed(tmp_path)
    d1 = decision_digest(build_decision_material(tmp_path))
    d2 = decision_digest(build_decision_material(tmp_path))
    assert d1 == d2


def test_decision_digest_is_invariant_to_entry_authoring_order(tmp_path: Path) -> None:
    # design §9 (sorted projections): `_project_inputs` sorts `entries` (by `eid`) before the
    # digest is taken over them, so the digest is a function of decision CONTENT, not scan/authoring
    # order. `test_decision_digest_is_stable_across_runs` re-scans the SAME unmodified directory
    # twice, so it passes trivially even with the `sorted(...)` deleted -- it never witnesses the
    # order-invariance itself. This test targets `_project_inputs` directly: same `SupersessionInputs`
    # content, `entries` tuple REVERSED, and the resulting digests must still match.
    _seed(tmp_path)
    inputs = load_supersession_inputs(tmp_path)
    reversed_inputs = dataclasses.replace(inputs, entries=tuple(reversed(inputs.entries)))
    assert reversed_inputs.entries != inputs.entries  # sanity: the reordering is real, not a no-op
    assert decision_digest(_project_inputs(inputs)) == decision_digest(_project_inputs(reversed_inputs))


def test_decision_digest_changes_when_a_material_field_changes(tmp_path: Path) -> None:
    _seed(tmp_path)
    before = decision_digest(build_decision_material(tmp_path))
    p = tmp_path / "entities" / "interpretations" / "0002-b.md"
    fm = yaml.safe_load(p.read_text(encoding="utf-8").split("---\n", 2)[1])
    fm["status"] = "superseded"
    p.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8")
    after = decision_digest(build_decision_material(tmp_path))
    assert before != after


def test_non_projected_field_change_does_not_move_the_digest(tmp_path: Path) -> None:
    # design §9: a frontmatter change to a field NOT in the projection (e.g. `title`) leaves the
    # decision digest unchanged — the digest surface is exactly the decision surface, no more.
    _seed(tmp_path)
    before = decision_digest(build_decision_material(tmp_path))
    p = tmp_path / "entities" / "interpretations" / "0001-a.md"
    fm = yaml.safe_load(p.read_text(encoding="utf-8").split("---\n", 2)[1])
    fm["title"] = "A COMPLETELY DIFFERENT TITLE"  # title is not part of the decision projection
    p.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8")
    after = decision_digest(build_decision_material(tmp_path))
    assert before == after


def test_material_admitted_edges_never_collapse_below_the_audit_count(tmp_path: Path) -> None:
    # design §9 (duplicates preserved): a corpus with a repeated supersedes target must yield a material
    # whose admitted-edge count equals the audit's relation count — the projection never collapses
    # admitted relations to a unique set.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-b\n"
        "  - predicate: sci:supersedes\n    target: interpretation:0002-b\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    inputs = load_supersession_inputs(tmp_path)
    mat = build_decision_material(tmp_path)
    assert len(mat.admitted_supersedes) == len(inputs.audit.relations(_SUPERSEDES))  # no collapsing
    assert any(e.src == "interpretation:0001-a" and e.dst == "interpretation:0002-b"
               for e in mat.admitted_supersedes)


def test_material_captures_authored_superseded_by_not_just_edges(tmp_path: Path) -> None:
    # 0002-b authors a superseded_by inverse; the material must carry that per-entry projection
    # so the derived unbacked-inverse rule (Task 9) can be reproduced from the digest alone.
    _seed(tmp_path)
    mat = build_decision_material(tmp_path)
    b = [e for e in mat.entries if e.eid == "interpretation:0002-b"][0]
    assert b.superseded_by_raw == "interpretation:0001-a"
    assert b.superseded_by_canonical == "interpretation:0001-a"


def test_material_preserves_the_admitted_relation_stream(tmp_path: Path) -> None:
    # The admitted-edge projection must count admitted relations, NOT a collapsed edge set —
    # collapsing to a set is the degree-miscount bug the graph builder documents.
    _seed(tmp_path)
    inputs = load_supersession_inputs(tmp_path)
    mat = build_decision_material(tmp_path)
    assert len(mat.admitted_supersedes) == len(inputs.audit.relations(_SUPERSEDES))


def test_build_decision_material_does_not_build_a_graph(monkeypatch, tmp_path: Path) -> None:
    # Guardrail for finding 2: the material is the INPUT projection; it must not be derived
    # from the graph OUTPUT.
    import science_tool.consolidation as c
    _seed(tmp_path)

    def _boom(*a, **k):
        raise AssertionError("build_decision_material must not call build_supersedes_graph")

    monkeypatch.setattr(c, "build_supersedes_graph", _boom)
    build_decision_material(tmp_path)  # must not raise


def _all_fields(g):
    return {
        "linear": [(c.survivor, c.superseded) for c in g.linear],
        "non_linear": [(n.nodes, n.reason) for n in g.non_linear],
        "status_by_id": dict(g.status_by_id),
        "kind_by_id": dict(g.kind_by_id),
        "edges": sorted(g.edges),
        "superseder_by_id": dict(g.superseder_by_id),
        "superseded_by_id": dict(g.superseded_by_id),
        "invalid": [(d.code, d.subject, d.object, d.message) for d in g.invalid],
        "archived_targets": list(g.archived_targets),
        "unmanaged_targets": list(g.unmanaged_targets),
        "unbacked_inverses": list(g.unbacked_inverses),
        "supported_kinds": sorted(g.supported_kinds),  # I4: the policy field must agree too
    }


def test_graph_from_material_equals_live_on_every_field(tmp_path: Path) -> None:
    _seed(tmp_path)
    live = build_supersedes_graph(load_supersession_inputs(tmp_path))
    mat = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    assert _all_fields(live) == _all_fields(mat)  # every decision/report field, not a subset


def test_graph_from_material_has_empty_path_by_id(tmp_path: Path) -> None:
    _seed(tmp_path)
    mat = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    assert dict(mat.path_by_id) == {}  # paths are not decision-bearing; gate B never reads them


def test_disposition_report_from_material_matches_mark_superseded(tmp_path: Path) -> None:
    # The disposition helper is a pure function of the graph: driving it from the material-derived
    # graph must yield the same dry-run report as the filesystem-driven mark_superseded.
    from science_tool.consolidation import _disposition_report, mark_superseded
    _seed(tmp_path)
    mat_graph = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    assert _disposition_report(mat_graph, ids=None) == mark_superseded(tmp_path, ids=None, apply=False)


def test_material_admitted_edges_are_canonically_sorted(tmp_path: Path) -> None:
    # Pin the NEW canonical (sorted) order of a multi-item list, per the 0.5.0 ordering ratification.
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True)
    (d / "0001-a.md").write_text(
        "---\nid: interpretation:0001-a\nkind: interpretation\ntitle: A\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0004-d\n---\nbody\n",
        encoding="utf-8")
    (d / "0002-b.md").write_text(
        "---\nid: interpretation:0002-b\nkind: interpretation\ntitle: B\nstatus: active\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0003-c\n---\nbody\n",
        encoding="utf-8")
    (d / "0003-c.md").write_text(
        "---\nid: interpretation:0003-c\nkind: interpretation\ntitle: C\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    (d / "0004-d.md").write_text(
        "---\nid: interpretation:0004-d\nkind: interpretation\ntitle: D\nstatus: active\n---\nbody\n",
        encoding="utf-8")
    mat = build_decision_material(tmp_path)
    keys = [(e.src, e.dst, e.source_path) for e in mat.admitted_supersedes]
    assert len(keys) == 2
    assert keys == sorted(keys)  # canonical order, deterministic across runs


def test_material_carries_supported_kinds_and_digest_covers_the_policy(monkeypatch, tmp_path: Path) -> None:
    # I4: the auto-apply supported-kind policy is part of the authenticated decision surface. It is
    # serialized (sorted) into the material, and changing it flips the digest — so a policy shift
    # between preview and apply is caught as drift, not silently applied.
    import science_tool.consolidation as c
    _seed(tmp_path)
    mat = build_decision_material(tmp_path)
    assert "interpretation" in mat.supported_kinds
    assert mat.supported_kinds == sorted(mat.supported_kinds)  # canonical
    before = decision_digest(mat)
    extended = dict(c._STATUS_VALUES)
    extended["zzz-fake-kind"] = frozenset({c._SUPERSEDED})  # a new auto-apply-eligible kind
    monkeypatch.setattr(c, "_STATUS_VALUES", extended)
    after = decision_digest(build_decision_material(tmp_path))
    assert before != after  # the policy change moved the digest


def test_disposition_reads_supported_kinds_from_the_graph_not_the_module(monkeypatch, tmp_path: Path) -> None:
    # _disposition_report must consult graph.supported_kinds (authenticated), not the live module
    # policy. Neutralizing the module function while the graph still carries the policy keeps the
    # disposition correct — proving the read moved onto the material.
    import science_tool.consolidation as c
    _seed(tmp_path)
    graph = build_supersedes_graph_from_material(build_decision_material(tmp_path))
    monkeypatch.setattr(c, "_supports_superseded", lambda kind: False)  # would empty to_mark if consulted
    report = c._disposition_report(graph, ids=None)
    assert report["to_mark"]  # still non-empty: the policy came from the graph, not the patched module


def test_disposition_report_sorts_the_four_secondary_lists_regardless_of_graph_order() -> None:
    # I7: the release-note behavior change. The four secondary report lists are emitted in canonical
    # sorted order even when the graph presents them in a NON-canonical order — so removing the sort
    # in _disposition_report fails this. Each list below is supplied reverse-of-canonical on purpose.
    from types import MappingProxyType

    from science_tool.consolidation import SupersedesGraph, _disposition_report
    from science_tool.graph.relation_audit import RelationDefect

    g = SupersedesGraph(
        linear=(), non_linear=(),
        status_by_id=MappingProxyType({}), kind_by_id=MappingProxyType({}),
        path_by_id=MappingProxyType({}), edges=frozenset(),
        superseder_by_id=MappingProxyType({}), superseded_by_id=MappingProxyType({}),
        invalid=(
            RelationDefect(code="invalid_relation", path="z.md", subject="interpretation:0009",
                           predicate="sci:supersedes", object="x", message="m"),
            RelationDefect(code="invalid_relation", path="a.md", subject="interpretation:0001",
                           predicate="sci:supersedes", object="x", message="m"),
        ),
        archived_targets=(
            {"id": "interpretation:0009", "superseder": "interpretation:0001", "path": "z", "reason": "r"},
            {"id": "interpretation:0002", "superseder": "interpretation:0003", "path": "a", "reason": "r"},
        ),
        unmanaged_targets=(
            {"id": "interpretation:0008", "superseder": "s", "path": "z", "reason": "r"},
            {"id": "interpretation:0004", "superseder": "s", "path": "a", "reason": "r"},
        ),
        unbacked_inverses=(
            {"id": "interpretation:0007", "superseder": "s", "reason": "r"},
            {"id": "interpretation:0003", "superseder": "s", "reason": "r"},
        ),
        supported_kinds=frozenset({"interpretation"}),
    )
    rep = _disposition_report(g, ids=None)
    assert [d["path"] for d in rep["invalid_relations"]] == ["a.md", "z.md"]
    assert [a["id"] for a in rep["archived_targets"]] == ["interpretation:0002", "interpretation:0009"]
    assert [u["id"] for u in rep["unmanaged_targets"]] == ["interpretation:0004", "interpretation:0008"]
    assert [u["id"] for u in rep["unbacked_inverses"]] == ["interpretation:0003", "interpretation:0007"]

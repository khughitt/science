from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

from science_tool.consolidation import (
    _project_inputs, _SUPERSEDES, build_decision_material, decision_digest,
    load_supersession_inputs,
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

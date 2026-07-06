from __future__ import annotations

from pathlib import Path

from science_tool.graph.health import build_health_report, collect_unresolved_refs
from science_tool.graph.materialize import materialization_audit


def _seed(root: Path, name: str = "proj") -> None:
    (root / "science.yaml").write_text(
        f"name: {name}\nprofile: research\nknowledge_profiles: {{local: local}}\n", encoding="utf-8"
    )


def _md(root: Path, rel: str, cid: str, kind: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\nkind: "{kind}"\ntitle: "{cid}"\n---\n', encoding="utf-8")


def _duplicate_owner(root: Path) -> None:
    _seed(root)
    _md(root, "entities/questions/q1.md", "question:q1", "question")
    _md(root, "entities/questions/q1-duplicate.md", "question:q1", "question")


def test_materialization_audit_reports_collision_without_crashing(tmp_path: Path) -> None:
    _duplicate_owner(tmp_path)
    rows, has_failures = materialization_audit(tmp_path)  # must not raise
    assert has_failures is True
    collision = [r for r in rows if r["check"] == "identity_collision" and r["source"] == "question:q1"]
    assert len(collision) == 1
    assert collision[0]["status"] == "fail"


def test_collect_unresolved_refs_excludes_identity_collision(tmp_path: Path) -> None:
    _duplicate_owner(tmp_path)
    refs = collect_unresolved_refs(tmp_path)  # must not raise
    # the collision is NOT mislabeled as an unresolved reference (e.g. to "proj")
    # `collect_unresolved_refs` returns a list of `UnresolvedRef` TypedDicts.
    assert all(ref["target"] != "proj" for ref in refs)


def test_build_health_report_diagnostic_load_is_nonstrict(tmp_path: Path) -> None:
    _duplicate_owner(tmp_path)
    report = build_health_report(tmp_path)  # must not raise
    # `build_health_report` returns a HealthReport dict; it has no `project_root`
    # key, so assert on a real key that proves the report assembled successfully.
    assert isinstance(report["total_issues"], int)

from __future__ import annotations

from pathlib import Path

from science_model.skill_coverage import EnrollmentStatus

from science_tool.graph.sources import load_project_sources
from science_tool.skills_coverage.evidence import project_evidence


def _gen3_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project, write_markdown_entity

    seed_project(root)
    # Pin gen-3 so provided_capabilities validates and skills_loaded reifies.
    cfg = root / "science.yaml"
    cfg.write_text(cfg.read_text() + "\nentity_schema_version: 3\n", encoding="utf-8")
    write_markdown_entity(root, "entities/datasets/tagged.md", {
        "id": "dataset:tagged", "kind": "dataset",
        "title": "Tagged dataset",
        "provided_capabilities": [{"data_product": "data-product:child-a"}],
    }, "A tagged dataset.")
    write_markdown_entity(root, "entities/datasets/bare.md", {
        "id": "dataset:bare", "kind": "dataset",
        "title": "Bare dataset",
    }, "An untagged dataset.")
    write_markdown_entity(root, "entities/datasets/scoped.md", {
        "id": "dataset:scoped", "kind": "dataset", "capability_scope": "reference-only",
        "title": "Scoped dataset",
    }, "A dataset whose empty capabilities are intentional.")
    write_markdown_entity(root, "entities/plans/0001-p.md", {
        "id": "plan:0001-p", "kind": "plan",
        "title": "Plan p",
        "related": ["entity-cli-test:dataset:tagged", "dataset:bare", "dataset:scoped"],
        "skills_loaded": [{"id": "bio-ca-qa", "reason": "QA the scRNA measurement."}],
    }, "A plan that relates to three datasets.")


def test_project_evidence_union_edge_and_untagged(tmp_path: Path) -> None:
    _gen3_project(tmp_path)
    sources = load_project_sources(tmp_path, include_commons=True)
    ev = project_evidence("proj", sources)
    assert ev.enrollment == EnrollmentStatus.ENROLLED
    # A scoped related dataset ref -> term usage via the union edge, no dataset_usage authored.
    assert any(t.dataset_ref == "dataset:tagged" and t.term == "data-product:child-a" and t.owned
               for t in ev.term_usages)
    # related:dataset:bare -> untagged usage (owned, no capability_scope)
    assert any(u.dataset_ref == "dataset:bare" for u in ev.untagged_usages)
    # related:dataset:scoped -> NOT untagged debt (capability_scope honored)
    assert all(u.dataset_ref != "dataset:scoped" for u in ev.untagged_usages)
    # skills_loaded grouped per plan
    assert ev.plan_loaded_skills[0].skill_ids == ("bio-ca-qa",)


def test_project_evidence_unresolved_related_is_diagnostic(tmp_path: Path) -> None:
    from _fixtures.entity_helpers import write_markdown_entity

    _gen3_project(tmp_path)
    write_markdown_entity(tmp_path, "entities/plans/0002-q.md", {
        "id": "plan:0002-q", "kind": "plan", "title": "Plan q",
        "related": ["dataset:does-not-exist"],
    }, "A plan relating to a missing dataset.")
    sources = load_project_sources(tmp_path, include_commons=True)
    ev = project_evidence("proj", sources)
    assert any(u.ref == "dataset:does-not-exist" for u in ev.unresolved_related_refs)

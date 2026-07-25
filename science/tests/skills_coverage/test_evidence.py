from __future__ import annotations

from pathlib import Path

import pytest

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
        "id": "dataset:scoped", "kind": "dataset", "capability_scope": "reference-substrate",
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


def test_project_evidence_unknown_scope_does_not_suppress_unmapped(
    tmp_path: Path,
) -> None:
    from _fixtures.entity_helpers import write_markdown_entity

    _gen3_project(tmp_path)
    write_markdown_entity(tmp_path, "entities/datasets/unknown-scope.md", {
        "id": "dataset:unknown-scope",
        "kind": "dataset",
        "capability_scope": "unknown-scope",
        "title": "Dataset with unknown scope",
    }, "An untagged dataset with an invalid scope marker.")
    write_markdown_entity(tmp_path, "entities/plans/0002-q.md", {
        "id": "plan:0002-q",
        "kind": "plan",
        "title": "Plan q",
        "related": ["dataset:unknown-scope"],
    }, "A plan that uses the dataset with an unknown scope.")

    sources = load_project_sources(tmp_path, include_commons=True)
    evidence = project_evidence("proj", sources)

    assert any(
        usage.dataset_ref == "dataset:unknown-scope"
        for usage in evidence.untagged_usages
    )


def test_project_evidence_dangling_typed_dataset_usage_is_a_hard_error(
    tmp_path: Path,
) -> None:
    from _fixtures.entity_helpers import write_markdown_entity
    from science_tool.skills_coverage.evidence import SkillCoverageScanError

    _gen3_project(tmp_path)
    write_markdown_entity(tmp_path, "entities/plans/0002-q.md", {
        "id": "plan:0002-q",
        "kind": "plan",
        "title": "Plan q",
        "dataset_usage": [{"ref": "dataset:does-not-exist", "role": "analyzed"}],
    }, "A plan with a dangling typed dataset usage.")

    sources = load_project_sources(tmp_path, include_commons=True)

    with pytest.raises(
        SkillCoverageScanError,
        match=r"plan:0002-q dataset_usage ref .*dataset:does-not-exist.* does not resolve",
    ):
        project_evidence("proj", sources)


def test_project_evidence_commons_dataset_is_not_owned_or_unmapped(
    tmp_path: Path,
) -> None:
    _gen3_project(tmp_path)
    sources = load_project_sources(tmp_path, include_commons=True)
    sources.entity_source_adapters["dataset:tagged"] = "commons-merged"
    sources.entity_source_adapters["dataset:bare"] = "commons-merged"

    evidence = project_evidence("proj", sources)

    tagged = [
        usage
        for usage in evidence.term_usages
        if usage.dataset_ref == "dataset:tagged"
    ]
    assert tagged and all(not usage.owned for usage in tagged)
    assert all(
        usage.dataset_ref != "dataset:bare"
        for usage in evidence.untagged_usages
    )

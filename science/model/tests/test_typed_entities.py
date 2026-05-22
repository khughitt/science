"""Tests for Science-core typed entities per spec §Typed Entity Model.

Per controller directive: fields already on base Entity are inherited, not
redeclared. Invariants (@model_validator) live on typed subclasses (or are
inherited from Entity when they're kind-gated).
"""

from __future__ import annotations


import pytest

from science_model.entities import (
    DatasetEntity,
    Entity,
    EntityType,
    PaperEntity,
    ProjectEntity,
    ResearchPackageEntity,
    TaskEntity,
    WorkflowRunEntity,
)
from science_model.packages.schema import AccessBlock


def _minimal(kind: EntityType, id_: str) -> dict:
    return {
        "id": id_,
        "canonical_id": id_,
        "kind": kind.value,
        "type": kind,
        "title": id_,
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": f"{id_}.md",
    }


def test_task_entity_extends_project_entity() -> None:
    t = TaskEntity(**_minimal(EntityType.TASK, "task:t01"))
    assert isinstance(t, ProjectEntity)
    assert isinstance(t, Entity)


def test_dataset_entity_extends_project_entity() -> None:
    ds = DatasetEntity(**_minimal(EntityType.DATASET, "dataset:ds01"))
    assert isinstance(ds, ProjectEntity)


def test_dataset_entity_enforces_invariant_7_origin_external_requires_access() -> None:
    """Invariant #7 from rev 2.2: origin=external → access required."""
    with pytest.raises(ValueError, match="origin=external requires an access block"):
        DatasetEntity(
            **_minimal(EntityType.DATASET, "dataset:ds01"),
            origin="external",
            access=None,
        )


def test_dataset_entity_accepts_valid_external_origin() -> None:
    ds = DatasetEntity(
        **_minimal(EntityType.DATASET, "dataset:ds01"),
        origin="external",
        access=AccessBlock(level="public", verified=False),
    )
    assert ds.origin == "external"


def test_paper_entity_coerces_scalar_author_to_list() -> None:
    paper = PaperEntity(
        **_minimal(EntityType.PAPER, "paper:Ang2024"),
        authors="Ang et al.",
    )

    assert paper.authors == ["Ang et al."]


def test_paper_entity_normalizes_null_identifier_strings_to_defaults() -> None:
    paper = PaperEntity(
        **_minimal(EntityType.PAPER, "paper:Kurowska2024"),
        pmid=None,
    )

    assert paper.pmid == ""


def test_workflow_run_entity_extends_project_entity() -> None:
    wr = WorkflowRunEntity(**_minimal(EntityType.WORKFLOW_RUN, "workflow-run:r1"))
    assert isinstance(wr, ProjectEntity)


def test_research_package_entity_extends_project_entity() -> None:
    rp = ResearchPackageEntity(**_minimal(EntityType.RESEARCH_PACKAGE, "research-package:rp1"))
    assert isinstance(rp, ProjectEntity)


def test_typed_entities_do_not_cross_inherit() -> None:
    """TaskEntity and DatasetEntity should be independent siblings under ProjectEntity."""
    assert not issubclass(TaskEntity, DatasetEntity)
    assert not issubclass(DatasetEntity, TaskEntity)


def test_generic_entity_with_kind_dataset_does_not_own_dataset_invariants() -> None:
    entity = Entity(
        id="dataset:ds01",
        canonical_id="dataset:ds01",
        kind="dataset",
        type=EntityType.DATASET,
        title="DS1",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/datasets/ds01.md",
        origin="external",
    )
    assert entity.origin == "external"


def test_code_file_entity_defaults_and_fields() -> None:
    from science_model.entities import CodeFileEntity

    cf = CodeFileEntity(**_minimal(EntityType.CODE_FILE, "code-file:stages/run.py"))
    assert isinstance(cf, ProjectEntity)
    assert cf.decision_bearing is None
    assert cf.executable is False
    assert cf.task_ids == []

    cf2 = CodeFileEntity(
        **_minimal(EntityType.CODE_FILE, "code-file:stages/run.py"),
        decision_bearing=True,
        task_ids=["t491"],
    )
    assert cf2.decision_bearing is True
    assert cf2.task_ids == ["t491"]

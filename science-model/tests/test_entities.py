from datetime import date
from science_model.entities import Entity, EntityType


def test_entity_round_trip():
    e = Entity(
        id="hypothesis:h01-foo",
        type=EntityType.HYPOTHESIS,
        title="Test hypothesis",
        status="proposed",
        project="my-project",
        tags=["genomics"],
        ontology_terms=["GO:0006915"],
        created=date(2026, 3, 1),
        updated=date(2026, 3, 10),
        related=["question:q01"],
        source_refs=[],
        content_preview="A test hypothesis about...",
        file_path="specs/hypotheses/h01-foo.md",
    )
    assert e.type == EntityType.HYPOTHESIS
    assert e.id == "hypothesis:h01-foo"
    d = e.model_dump()
    assert d["type"] == "hypothesis"
    e2 = Entity.model_validate(d)
    assert e2 == e


def test_entity_optional_fields_default_none():
    e = Entity(
        id="concept:foo",
        type=EntityType.CONCEPT,
        title="Foo",
        project="p",
        tags=[],
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/topics/foo.md",
    )
    assert e.status is None
    assert e.domain is None
    assert e.maturity is None
    assert e.confidence is None
    assert e.datasets is None
    assert e.created is None
    assert e.updated is None


def test_workflow_entity_types_exist():
    """New workflow entity types are defined and serialize correctly."""
    assert EntityType.WORKFLOW == "workflow"
    assert EntityType.WORKFLOW_RUN == "workflow-run"
    assert EntityType.WORKFLOW_STEP == "workflow-step"


def test_pipeline_step_renamed_to_workflow_step():
    """PIPELINE_STEP is removed; WORKFLOW_STEP replaces it."""
    assert not hasattr(EntityType, "PIPELINE_STEP")
    assert EntityType.WORKFLOW_STEP == "workflow-step"


def test_workflow_run_entity_round_trip():
    """A workflow-run entity can be created and round-tripped."""
    e = Entity(
        id="workflow-run:a001-protein-sp-tmr",
        type=EntityType.WORKFLOW_RUN,
        title="Protein SP/TMR feature evaluation",
        status="complete",
        project="seq-feats",
        tags=["feature-eval"],
        ontology_terms=[],
        related=["workflow:feature-eval"],
        source_refs=[],
        content_preview="Feature evaluation run for SP and TMR",
        file_path="results/feature-eval/a001-protein-sp-tmr/datapackage.json",
    )
    d = e.model_dump()
    assert d["type"] == "workflow-run"
    e2 = Entity.model_validate(d)
    assert e2 == e

from datetime import date

import pytest
from pydantic import ValidationError

from science_model.entities import Entity, EntityType, MechanismEntity, core_entity_type_for_kind
from science_model.identity import EntityScope, ExternalId


def test_entity_round_trip():
    e = Entity(
        id="hypothesis:h01-foo",
        kind="hypothesis",
        type=EntityType.HYPOTHESIS,
        title="Test hypothesis",
        status="proposed",
        project="my-project",
        ontology_terms=["GO:0006915"],
        created=date(2026, 3, 1),
        updated=date(2026, 3, 10),
        related=["question:q01"],
        source_refs=[],
        content_preview="A test hypothesis about...",
        file_path="specs/hypotheses/h01-foo.md",
    )
    assert e.kind == "hypothesis"
    assert e.type == EntityType.HYPOTHESIS
    assert e.id == "hypothesis:h01-foo"
    d = e.model_dump()
    assert d["type"] == "hypothesis"
    e2 = Entity.model_validate(d)
    assert e2 == e


def test_entity_optional_fields_default_none():
    e = Entity(
        id="concept:foo",
        kind="concept",
        type=EntityType.CONCEPT,
        title="Foo",
        project="p",
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


def test_entity_accepts_identity_fields() -> None:
    e = Entity(
        id="gene:EZH2",
        canonical_id="gene:EZH2",
        kind="gene",
        type=None,
        title="EZH2",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/genes/EZH2.md",
        primary_external_id=ExternalId(
            source="HGNC",
            id="3527",
            curie="HGNC:3527",
            provenance="manual",
        ),
        xrefs=[
            ExternalId(
                source="NCBIGene",
                id="2146",
                curie="NCBIGene:2146",
                provenance="manual",
            )
        ],
        scope=EntityScope.SHARED,
        provisional=True,
        review_after=date(2026, 5, 1),
        deprecated_ids=["gene:ENX1"],
        replaced_by="gene:EZH2-v2",
        taxon="NCBITaxon:9606",
    )
    assert e.scope == EntityScope.SHARED
    assert e.primary_external_id is not None
    assert e.primary_external_id.curie == "HGNC:3527"
    assert e.xrefs[0].curie == "NCBIGene:2146"


def test_entity_rejects_self_deprecated_id() -> None:
    with pytest.raises(ValidationError, match="deprecated"):
        Entity(
            id="concept:chromatin",
            canonical_id="concept:chromatin",
            kind="concept",
            type=EntityType.CONCEPT,
            title="Chromatin",
            project="p",
            ontology_terms=[],
            related=[],
            source_refs=[],
            content_preview="",
            file_path="doc/concepts/chromatin.md",
            deprecated_ids=["concept:chromatin"],
        )


def test_versioned_external_id_keeps_version_metadata() -> None:
    identity = ExternalId(
        source="ENSEMBL",
        id="ENST00000381578",
        curie="ENSEMBL:ENST00000381578",
        version="7",
        provenance="manual",
    )
    assert identity.id == "ENST00000381578"
    assert identity.version == "7"


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
        kind="workflow-run",
        type=EntityType.WORKFLOW_RUN,
        title="Protein SP/TMR feature evaluation",
        status="complete",
        project="seq-feats",
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


def test_proposition_entity_type():
    assert EntityType.PROPOSITION == "proposition"
    assert EntityType("proposition") == EntityType.PROPOSITION


def test_observation_entity_type():
    assert EntityType.OBSERVATION == "observation"
    assert EntityType("observation") == EntityType.OBSERVATION


def test_finding_entity_type():
    assert EntityType.FINDING == "finding"
    assert EntityType("finding") == EntityType.FINDING


def test_story_entity_type():
    assert EntityType.STORY == "story"
    assert EntityType("story") == EntityType.STORY


def test_removed_types_absent():
    """Retired entity types are removed from EntityType."""
    assert not hasattr(EntityType, "CLAIM")
    assert not hasattr(EntityType, "RELATION_CLAIM")
    assert not hasattr(EntityType, "EVIDENCE")
    assert not hasattr(EntityType, "ARTIFACT")
    assert not hasattr(EntityType, "COMPARISON")
    assert not hasattr(EntityType, "BIAS_AUDIT")
    assert not hasattr(EntityType, "PRE_REGISTRATION")


def test_pre_registered_fields():
    e = Entity(
        id="proposition:p01",
        kind="proposition",
        type=EntityType.PROPOSITION,
        title="Test",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/p01.md",
        pre_registered=True,
        pre_registered_date=date(2026, 4, 1),
    )
    assert e.pre_registered is True
    assert e.pre_registered_date == date(2026, 4, 1)


def test_pre_registered_defaults_false():
    e = Entity(
        id="proposition:p02",
        kind="proposition",
        type=EntityType.PROPOSITION,
        title="Test",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/p02.md",
    )
    assert e.pre_registered is False
    assert e.pre_registered_date is None


def test_new_types_accessible_from_package():
    """New entity types are accessible via the top-level import."""
    from science_model import EntityType

    assert EntityType.WORKFLOW == "workflow"
    assert EntityType.WORKFLOW_RUN == "workflow-run"
    assert EntityType.WORKFLOW_STEP == "workflow-step"


def test_entity_has_no_tags_field():
    """After unification, Entity should not have a tags field in its schema."""
    assert "tags" not in Entity.model_fields


def test_core_entity_type_for_kind_returns_none_for_domain_kind() -> None:
    assert core_entity_type_for_kind("gene") is None


def test_entity_rejects_mismatched_kind_and_type() -> None:
    with pytest.raises(ValueError, match="kind/type"):
        Entity(
            id="gene:phf19",
            canonical_id="gene:phf19",
            kind="gene",
            type=EntityType.TASK,
            title="PHF19",
            project="demo",
            ontology_terms=[],
            related=[],
            source_refs=[],
            content_preview="",
            file_path="doc/phf19.md",
        )


VALID_MECHANISM_RAW = {
    "id": "mechanism:phf19-prc2-ifn-immunotherapy",
    "canonical_id": "mechanism:phf19-prc2-ifn-immunotherapy",
    "kind": "mechanism",
    "type": EntityType.MECHANISM,
    "title": "PHF19 / PRC2 / IFN / immunotherapy",
    "project": "mm30",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
    "content_preview": "Mechanistic summary.",
    "file_path": "doc/mechanisms/phf19-prc2-ifn-immunotherapy.md",
    "participants": ["protein:PHF19", "concept:prc2-complex"],
    "propositions": ["proposition:ifn-silencing"],
    "summary": "PHF19-PRC2 dampens IFN signaling relevant to immunotherapy.",
}


def test_mechanism_entity_requires_participants_and_propositions() -> None:
    entity = MechanismEntity.model_validate(VALID_MECHANISM_RAW)
    assert entity.kind == "mechanism"
    assert entity.type == EntityType.MECHANISM
    assert entity.participants == ["protein:PHF19", "concept:prc2-complex"]
    assert entity.propositions == ["proposition:ifn-silencing"]


def test_mechanism_entity_rejects_single_participant() -> None:
    with pytest.raises(ValidationError, match="at least two participants"):
        MechanismEntity.model_validate({**VALID_MECHANISM_RAW, "participants": ["concept:only-one"]})


def test_mechanism_entity_rejects_missing_propositions() -> None:
    with pytest.raises(ValidationError, match="at least one proposition"):
        MechanismEntity.model_validate({**VALID_MECHANISM_RAW, "propositions": []})


def test_mechanism_entity_rejects_empty_summary() -> None:
    with pytest.raises(ValidationError, match="non-empty summary"):
        MechanismEntity.model_validate({**VALID_MECHANISM_RAW, "summary": "  "})

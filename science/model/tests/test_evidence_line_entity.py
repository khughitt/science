"""Tests for EvidenceLineEntity model + EntityType.EVIDENCE_LINE."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import (
    Entity,
    EntityType,
    EvidenceLineEntity,
    ProjectEntity,
    core_entity_type_for_kind,
)
from science_model.reasoning import (
    DisputeScope,
    EvidenceRole,
    EvidenceStance,
    EvidenceStrength,
    IndependenceTag,
)


def _minimal_evidence_line(id_: str = "evidence-line:e1") -> dict:
    return {
        "id": id_,
        "canonical_id": id_,
        "kind": "evidence-line",
        "type": EntityType.EVIDENCE_LINE,
        "title": "E1 supports P1",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "doc/evidence-lines/e1.md",
        "stance": "supports",
        "target": "proposition:p1",
    }


def test_evidence_line_entity_constructs() -> None:
    el = EvidenceLineEntity(**_minimal_evidence_line())
    assert isinstance(el, ProjectEntity)
    assert isinstance(el, Entity)


def test_evidence_line_entity_stance_roundtrip() -> None:
    el = EvidenceLineEntity(**_minimal_evidence_line())
    assert el.stance == EvidenceStance.SUPPORTS


def test_evidence_line_entity_target_roundtrip() -> None:
    el = EvidenceLineEntity(**_minimal_evidence_line())
    assert el.target == "proposition:p1"


def test_evidence_line_entity_optional_fields() -> None:
    el = EvidenceLineEntity(
        **_minimal_evidence_line(),
        source="paper:X",
        strength="strong",
        independence="independent",
        independence_group="g1",
        evidence_role="model_criticism",
        dispute_scope="generalization",
    )
    assert el.strength == EvidenceStrength.STRONG
    assert el.independence == IndependenceTag.INDEPENDENT
    assert el.dispute_scope == DisputeScope.GENERALIZATION
    assert el.independence_group == "g1"
    assert el.evidence_role == EvidenceRole.MODEL_CRITICISM


def test_evidence_line_entity_disputes_stance() -> None:
    el = EvidenceLineEntity(
        **{**_minimal_evidence_line(), "stance": "disputes"},
        dispute_scope="whole_claim",
    )
    assert el.stance == EvidenceStance.DISPUTES


def test_evidence_line_entity_shared_fields() -> None:
    el = EvidenceLineEntity(
        **_minimal_evidence_line(),
        shared_dataset="ds:X",
        shared_lab="lab-alpha",
        shared_platform="platform-Y",
        shared_cohort="cohort-Z",
    )
    assert el.shared_dataset == "ds:X"
    assert el.shared_lab == "lab-alpha"
    assert el.shared_platform == "platform-Y"
    assert el.shared_cohort == "cohort-Z"


def test_evidence_line_entity_defaults_for_optional_fields() -> None:
    el = EvidenceLineEntity(**_minimal_evidence_line())
    assert el.source is None
    assert el.strength is None
    assert el.independence is None
    assert el.dispute_scope is None
    assert el.shared_dataset is None
    assert el.shared_lab is None
    assert el.shared_platform is None
    assert el.shared_cohort is None


def test_core_entity_type_for_kind_resolves_evidence_line() -> None:
    assert core_entity_type_for_kind("evidence-line") == EntityType.EVIDENCE_LINE


def test_entity_type_evidence_line_value() -> None:
    assert EntityType.EVIDENCE_LINE.value == "evidence-line"


def test_stance_required() -> None:
    data = _minimal_evidence_line()
    del data["stance"]
    with pytest.raises(ValidationError):
        EvidenceLineEntity(**data)


def test_target_required() -> None:
    data = _minimal_evidence_line()
    del data["target"]
    with pytest.raises(ValidationError):
        EvidenceLineEntity(**data)

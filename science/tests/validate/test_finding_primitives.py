import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import (
    FindingRule,
    FindingSection,
    PathSubject,
    ProducerMetrics,
    ProjectSubject,
)

from science_tool.validate.findings import (
    CorrespondenceQualifiers,
    NumericVerificationMetrics,
    ProseAdvisoryQualifiers,
    ProseHitQualifiers,
    ValidationQualifiers,
    build_validation_finding,
    rule_kind_segment,
    validation_evidence,
    validation_subject,
)
from science_tool.validate.observations import (
    ValidationMetricObservation,
    ValidationNotice,
    ValidationObservationBatch,
)


class EmptyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")


SECTION = FindingSection(id="test", title="Test", section_order=1)
RULE = FindingRule(
    id="test.problem",
    severities={"warn"},
    subject_types={"path"},
    qualifier_schema=EmptyQualifiers,
    title="Problem",
    section=SECTION.id,
    display_order=1,
)


def test_validation_path_is_the_subject_and_line_is_evidence_only(tmp_path):
    absolute = tmp_path / "entities" / "papers" / "1.md"
    assert validation_subject(tmp_path, absolute) == PathSubject(path="entities/papers/1.md")
    evidence = validation_evidence(tmp_path, absolute, 7)
    assert evidence[0].path == "entities/papers/1.md"
    assert evidence[0].line == 7


def test_pathless_validation_result_is_project_scoped(tmp_path):
    assert validation_subject(tmp_path, None) == ProjectSubject()
    assert validation_evidence(tmp_path, None, None) == ()


def test_validation_path_without_a_line_has_no_evidence(tmp_path):
    assert validation_evidence(tmp_path, tmp_path / "science.yaml", None) == ()


def test_prose_advisory_count_is_not_an_identity_field():
    assert ProseAdvisoryQualifiers.model_fields.keys() == {"check", "count"}
    assert ProseHitQualifiers.model_fields.keys() == {
        "check",
        "match",
    }
    assert ValidationQualifiers.model_fields.keys() == {"key", "task"}
    assert CorrespondenceQualifiers.model_fields.keys() == {
        "task",
        "evidence_signature",
    }
    assert rule_kind_segment("canonical_parameter") == "canonical-parameter"
    assert rule_kind_segment("paper") == "paper"


def test_ordinary_validation_identity_key_is_required_explicitly():
    with pytest.raises(ValidationError):
        ValidationQualifiers.model_validate({"task": None})
    assert ValidationQualifiers.model_validate({"key": ["missing-field", "summary"], "task": None}).key == [
        "missing-field",
        "summary",
    ]


def test_build_validation_finding_uses_path_subject_and_location_evidence(tmp_path):
    finding = build_validation_finding(
        project_root=tmp_path,
        rule=RULE,
        severity="warn",
        path=tmp_path / "science.yaml",
        line=12,
        message="problem",
        qualifiers={},
    )
    assert finding.subject == PathSubject(path="science.yaml")
    assert finding.evidence[0].path == "science.yaml"
    assert finding.evidence[0].line == 12


def test_numeric_verification_metrics_rejects_negative_counts():
    with pytest.raises(ValidationError):
        NumericVerificationMetrics.model_validate({"verified": -1, "unverifiable": 0, "mismatch": 0, "error": 0})


def test_observation_batch_projects_findings_and_metrics_but_retains_notices():
    finding = RULE.build(
        subject=PathSubject(path="science.yaml"),
        severity="warn",
        qualifiers={},
        message="problem",
    )
    metrics = ValidationMetricObservation(metrics=ProducerMetrics(count=1))
    notice = ValidationNotice(path=None, line=None, message="checked one thing")
    batch = ValidationObservationBatch.from_observations((finding, metrics, notice))
    result = batch.producer_result()
    assert len(result.instrument.rows) == 1
    assert result.metrics.model_dump(mode="json") == {"count": 1}
    assert batch.notices == (notice,)


def test_observation_batch_rejects_two_metrics_observations():
    metric = ValidationMetricObservation(metrics=ProducerMetrics(count=1))
    with pytest.raises(ValueError, match="multiple metrics observations"):
        ValidationObservationBatch.from_observations((metric, metric))


def test_observation_batch_rejects_unsupported_observations():
    with pytest.raises(TypeError, match="unsupported validation observation object"):
        ValidationObservationBatch.from_observations((object(),))

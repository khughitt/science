import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import (
    FindingRule,
    FindingSection,
    ProducerMetrics,
    ProjectSubject,
)

from science_tool.findings.producers import (
    FindingProducer,
    FindingProducerResult,
    RegistryError,
    build_registry,
    validate_producer_result,
)
from science_tool.instruments import InstrumentResult


class EmptyQ(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CountMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


SECTION = FindingSection(id="test", title="Test", section_order=1)
RULE = FindingRule(
    id="test.problem",
    severities={"warn"},
    subject_types={"project"},
    qualifier_schema=EmptyQ,
    title="Problem",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="test-producer",
    namespace="health_checks",
    source_module="graph/health_checks/test_producer.py",
    rules=(RULE,),
    sections=(SECTION,),
    metrics_schema=CountMetrics,
)


def _registry():
    return build_registry([PRODUCER], active_kinds=frozenset())


def _finding(message="m"):
    return RULE.build(
        subject=ProjectSubject(),
        severity="warn",
        qualifiers={},
        message=message,
    )


@pytest.mark.parametrize(
    "wrong",
    [
        InstrumentResult.ok([_finding()]),
        (_finding(), {}),
        [_finding()],
        {"instrument": InstrumentResult.ok([_finding()]), "metrics": {}},
    ],
)
def test_registered_boundary_rejects_every_noncomposed_shape(wrong):
    with pytest.raises(TypeError, match="FindingProducerResult"):
        validate_producer_result(_registry(), "test-producer", wrong)


def test_wired_metrics_cross_the_declared_schema_strictly():
    valid = FindingProducerResult(
        instrument=InstrumentResult.ok([_finding()]),
        metrics=ProducerMetrics(count=2),
    )
    assert validate_producer_result(_registry(), "test-producer", valid) is valid
    invalid = FindingProducerResult(
        instrument=InstrumentResult.empty(),
        metrics=ProducerMetrics(count="2"),
    )
    with pytest.raises(RegistryError, match="metrics invalid"):
        validate_producer_result(_registry(), "test-producer", invalid)


def test_unwired_omits_metrics_even_when_schema_has_required_fields():
    result = FindingProducerResult(
        instrument=InstrumentResult.unwired(code="not-connected", reason="no source"),
    )
    assert validate_producer_result(_registry(), "test-producer", result) is result
    with pytest.raises(ValidationError, match="unwired producer cannot report metrics"):
        FindingProducerResult(
            instrument=InstrumentResult.unwired(code="not-connected"),
            metrics=ProducerMetrics(count=1),
        )


def test_same_identity_with_different_prose_is_rejected_at_the_producer():
    result = FindingProducerResult(
        instrument=InstrumentResult.ok([_finding("first"), _finding("second")]),
        metrics=ProducerMetrics(count=2),
    )
    with pytest.raises(RegistryError, match="duplicate finding identity"):
        validate_producer_result(_registry(), "test-producer", result)

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import FindingRule, FindingSection

from science_tool.findings.producers import (
    FindingProducer,
    RegistryError,
    build_registry,
)


class Q(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str


class M(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scanned: int


class OpenMetrics(BaseModel):
    scanned: int


SECTION = FindingSection(id="datasets", title="Datasets", section_order=300)


def _rule(rule_id="dataset.stale-review", order=100) -> FindingRule:
    return FindingRule(
        id=rule_id, severities={"warn"}, subject_types={"entity"},
        qualifier_schema=Q, identity_qualifiers=("field",),
        title="t", section="datasets", display_order=order,
    )


def _producer(pid="dataset_anomalies", rules=None, metrics_schema=M) -> FindingProducer:
    return FindingProducer(
        producer_id=pid, namespace="health_checks", rules=tuple(rules or [_rule()]),
        sections=(SECTION,), metrics_schema=metrics_schema, remediators=frozenset(),
    )


def test_registry_resolves_a_declared_rule():
    registry = build_registry([_producer()])
    assert registry.rule("dataset.stale-review").title == "t"


@pytest.mark.parametrize("metrics_schema", [OpenMetrics, BaseModel])
def test_producer_rejects_an_open_metrics_schema(metrics_schema):
    with pytest.raises(ValidationError, match="metrics schema"):
        _producer(metrics_schema=metrics_schema)


def test_producer_accepts_a_closed_metrics_schema():
    assert _producer().metrics_schema is M


def test_duplicate_rule_id_across_producers_fails():
    with pytest.raises(RegistryError, match="duplicate rule id"):
        build_registry([_producer(pid="a"), _producer(pid="b")])


def test_duplicate_producer_id_fails():
    with pytest.raises(RegistryError, match="duplicate producer id"):
        build_registry([_producer(), _producer(rules=[_rule("dataset.other")])])


def test_unknown_rule_lookup_fails_rather_than_returning_none():
    registry = build_registry([_producer()])
    with pytest.raises(RegistryError, match="undeclared rule"):
        registry.rule("dataset.never-declared")


def test_colliding_display_order_within_a_section_fails():
    with pytest.raises(RegistryError, match="display_order"):
        build_registry([
            _producer(rules=[_rule("dataset.a", 10), _rule("dataset.b", 10)])
        ])


def test_colliding_section_order_fails():
    other = FindingSection(id="tasks", title="Tasks", section_order=300)
    producer = FindingProducer(
        producer_id="p", namespace="health_checks", rules=(_rule(),),
        sections=(SECTION, other), metrics_schema=M, remediators=frozenset(),
    )
    with pytest.raises(RegistryError, match="section_order"):
        build_registry([producer])


def test_rule_naming_an_undeclared_section_fails():
    with pytest.raises(RegistryError, match="undeclared section"):
        build_registry([
            _producer(rules=[_rule("dataset.a")]).model_copy(update={"sections": ()})
        ])


def test_producer_remediation_without_a_registered_handler_fails():
    rule = FindingRule(
        id="dataset.fixable", severities={"warn"}, subject_types={"entity"},
        qualifier_schema=Q, identity_qualifiers=("field",), remediation="producer",
        remediator="fix_dataset", title="t", section="datasets", display_order=200,
    )
    with pytest.raises(RegistryError, match="remediator"):
        build_registry([_producer(rules=[rule])])


def test_sort_key_orders_by_section_then_display_order_not_by_name():
    alpha = FindingSection(id="zzz-last-alphabetically", title="Z", section_order=100)
    beta = FindingSection(id="aaa-first-alphabetically", title="A", section_order=200)
    producer = FindingProducer(
        producer_id="p", namespace="health_checks",
        rules=(
            FindingRule(id="z.rule", severities={"warn"}, subject_types={"project"},
                        qualifier_schema=Q, title="t", section=alpha.id, display_order=1),
            FindingRule(id="a.rule", severities={"warn"}, subject_types={"project"},
                        qualifier_schema=Q, title="t", section=beta.id, display_order=1),
        ),
        sections=(alpha, beta), metrics_schema=M, remediators=frozenset(),
    )
    registry = build_registry([producer])
    assert registry.sort_key("z.rule") < registry.sort_key("a.rule")


def test_metrics_are_validated_against_the_declared_schema():
    registry = build_registry([_producer()])
    registry.validate_metrics("dataset_anomalies", {"scanned": 3})
    with pytest.raises(RegistryError, match="metrics"):
        registry.validate_metrics("dataset_anomalies", {"scaned": 3})


def test_a_metric_of_the_wrong_type_is_refused_not_quietly_coerced():
    """A count that is sometimes a string is a count nothing can sum.

    `ProducerMetrics` is `extra="allow"` with no declared fields, so a metric is
    stored exactly as the report spelled it -- the producer's declared schema is the
    only thing that types it. Lax validation would accept `"3"` for `scanned: int`,
    report `3`, discard that model, and leave `"3"` to be rendered and compared.
    """
    registry = build_registry([_producer()])
    with pytest.raises(RegistryError, match="metrics invalid"):
        registry.validate_metrics("dataset_anomalies", {"scanned": "3"})


def test_the_registry_mappings_are_not_mutable():
    registry = build_registry([_producer()])
    with pytest.raises(TypeError):
        registry.rules_by_id["injected"] = _rule("dataset.injected")
    with pytest.raises(TypeError):
        registry.sections_by_id["injected"] = SECTION
    with pytest.raises(TypeError):
        registry.producers_by_id["injected"] = _producer()


def test_project_config_cannot_add_or_override_a_rule(tmp_path):
    # The registry reads nothing from the filesystem, environment, or project config.
    # This test is the assertion that it has no such input at all.
    import inspect

    import science_tool.findings.producers as module

    source = inspect.getsource(module)
    for forbidden in ("yaml", "project_config", "os.environ", "science.yaml"):
        assert forbidden not in source, (
            f"{forbidden!r} appears in producers.py; the registry must not be "
            "project-overridable (design §6)"
        )

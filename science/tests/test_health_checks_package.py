from science_tool.graph.health_checks import HEALTH_CHECKS
from science_tool.graph.health_checks.schema_invalid import SCHEMA_INVALID_PRODUCER


def test_health_check_order_is_explicit_and_stable() -> None:
    assert [check.name for check in HEALTH_CHECKS] == [
        "identity_policy",
        "entity_identity",
        "layered_claim_migration",
        "cross_paper_evidence",
        "managed_artifacts",
        "tooling_scaffold",
        "validate",
        "prose_epistemics",
        "agent_context",
        "unresolved_refs",
        "unregistered_ref_kinds",
        "lingering_tags",
        "dataset_anomalies",
        "legacy_task_type",
        "invalid_entity_aspects",
    ]


def test_each_health_check_has_one_matching_producer() -> None:
    assert all(check.producer.producer_id == check.name for check in HEALTH_CHECKS)
    assert len({check.producer.producer_id for check in HEALTH_CHECKS}) == len(HEALTH_CHECKS)
    assert SCHEMA_INVALID_PRODUCER.producer_id == "schema_invalid"


def test_health_section_orders_are_monotonic() -> None:
    orders = [
        check.producer.sections[0].section_order
        for check in HEALTH_CHECKS
        if check.producer.sections
    ]
    assert orders == sorted(orders)

import pytest

from science_tool.addressing import (
    Address,
    RefShape,
    classify_entity_ref,
    is_address,
    parse_address,
    render_uri,
)

LOCAL_KINDS = {"task", "hypothesis", "question", "meta", "topic"}
PROJECT_IDS = {"cbioportal", "multiple-myeloma", "natural-systems"}


def test_parse_artifact_address_keeps_two_part_shape() -> None:
    address = parse_address("cbioportal:topics/clonal-hematopoiesis-contamination")
    assert address == Address(project_id="cbioportal", artifact_id="topics/clonal-hematopoiesis-contamination")


def test_parse_legacy_two_part_entity_address_still_round_trips_as_artifact_address() -> None:
    address = parse_address("cbioportal:q014")
    assert address == Address(project_id="cbioportal", artifact_id="q014")


def test_render_uri_for_artifact_address() -> None:
    address = Address(project_id="multiple-myeloma", artifact_id="h003")
    assert render_uri(address) == "<cancer://multiple-myeloma/h003>"


def test_is_address_positive_for_artifacts() -> None:
    assert is_address("cbioportal:topics/clonal-hematopoiesis-contamination") is True


def test_is_address_negative() -> None:
    assert is_address("not an address") is False
    assert is_address("just-a-word") is False
    assert is_address("a:") is False
    assert is_address(":x") is False


def test_is_address_rejects_at_in_artifact() -> None:
    assert is_address("cbioportal:q014@v2") is False


def test_parse_invalid_address_raises() -> None:
    with pytest.raises(ValueError):
        parse_address("not an address")


def test_classifies_bare_task_shorthand_as_local_task() -> None:
    ref = classify_entity_ref("t123", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(raw="t123", shape="bare-task", kind="task", slug="t123")


def test_classifies_local_entity_ref() -> None:
    ref = classify_entity_ref("task:t123", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(raw="task:t123", shape="local-entity", kind="task", slug="t123")


def test_classifies_namespace_first_entity_ref() -> None:
    ref = classify_entity_ref("natural-systems:task:t335", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(
        raw="natural-systems:task:t335",
        shape="cross-project-entity",
        project_id="natural-systems",
        kind="task",
        slug="t335",
    )


def test_two_part_local_kind_wins_even_when_project_id_exists() -> None:
    ref = classify_entity_ref("meta:next-steps-2026-05-05", local_kinds=LOCAL_KINDS, project_ids={"meta"})
    assert ref == RefShape(
        raw="meta:next-steps-2026-05-05",
        shape="local-entity",
        kind="meta",
        slug="next-steps-2026-05-05",
    )


def test_classifies_legacy_two_part_cross_project_ref() -> None:
    ref = classify_entity_ref("cbioportal:q014", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(
        raw="cbioportal:q014",
        shape="legacy-cross-project",
        project_id="cbioportal",
        slug="q014",
    )


def test_classifies_unknown_three_part_namespace() -> None:
    ref = classify_entity_ref("unknown-project:task:t001", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(
        raw="unknown-project:task:t001",
        shape="unknown-namespace",
        project_id="unknown-project",
        kind="task",
        slug="t001",
    )


def test_classify_entity_ref_rejects_at_in_artifact() -> None:
    """`@` in the artifact position must not classify as any entity ref shape.

    Rationale: Decision 1 of the project-peers design reserves `@<version>` as
    a future suffix; allowing it in slugs today would conflict with the future
    versioning grammar.
    """
    from science_tool.addressing import classify_entity_ref

    result = classify_entity_ref(
        "task:t001@v2",
        local_kinds={"task"},
        project_ids=frozenset(),
    )
    assert result.shape == "non-entity"

from __future__ import annotations

from typing import Any

import pytest

from science_tool.labnote_view_contract import (
    HIDDEN_KIND_REASONS,
    PRODUCER_VIEW_SURFACES,
    VIEW_ID_RE,
    DescriptorError,
    descriptor_errors,
    route_for_view,
)


def test_contract_constants() -> None:
    assert PRODUCER_VIEW_SURFACES == frozenset({"explore", "findings"})
    assert HIDDEN_KIND_REASONS == frozenset({"declared_hidden", "fallback_hidden"})
    assert VIEW_ID_RE.pattern == r"^[a-z][a-z0-9_]*$"


@pytest.mark.parametrize(
    ("view_id", "surface", "expected"),
    [
        ("question", "explore", "/explore/question"),
        ("workflow_run", "explore", "/explore/workflow-run"),
        ("mechanism", "findings", "/findings/mechanism"),
        ("pre_registration", "explore", "/explore/pre-registration"),
    ],
)
def test_route_for_view_derives_the_conventional_route(
    view_id: str, surface: str, expected: str
) -> None:
    assert route_for_view(view_id, surface) == expected


@pytest.mark.parametrize("surface", ["analysis", "references", "", "Explore", "explore/"])
def test_route_for_view_rejects_surfaces_outside_the_closed_set(surface: str) -> None:
    with pytest.raises(ValueError, match="surface"):
        route_for_view("question", surface)


@pytest.mark.parametrize(
    "view_id", ["ResearchQuestion", "1question", "question-view", "question__VIEW", ""]
)
def test_route_for_view_rejects_ids_outside_the_contract(view_id: str) -> None:
    with pytest.raises(ValueError, match="view id"):
        route_for_view(view_id, "explore")


def _valid_descriptor() -> dict[str, Any]:
    return {
        "views": [
            {
                "id": "research_question",
                "label": "Research Questions",
                "surface": "explore",
                "entity_types": ["research_question"],
                "route": "/explore/research-question",
                "order": 500,
                "modules": [],
            }
        ],
        "hidden_kinds": [
            {
                "entity_type": "talk",
                "entity_count": 3,
                "reason": "fallback_hidden",
            }
        ],
    }


def _codes(views: object) -> list[str]:
    return sorted(error.code for error in descriptor_errors(views))


def test_valid_descriptor_has_no_errors() -> None:
    assert descriptor_errors(_valid_descriptor()) == []


def test_multi_kind_view_is_valid() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"][0]["entity_types"] = ["research_question", "question"]

    assert descriptor_errors(descriptor) == []


def test_absent_hidden_kinds_is_valid() -> None:
    descriptor = _valid_descriptor()
    del descriptor["hidden_kinds"]

    assert descriptor_errors(descriptor) == []


@pytest.mark.parametrize("document", ["not a mapping", ["views"], None, 7])
def test_non_mapping_document_is_invalid(document: object) -> None:
    errors = descriptor_errors(document)

    assert [error.code for error in errors] == ["views-json-invalid"]
    assert errors[0].identity is None


def test_non_list_views_is_invalid() -> None:
    errors = descriptor_errors({"views": {"id": "question"}})

    assert [error.code for error in errors] == ["views-json-invalid"]
    assert errors[0].identity is None


def test_non_mapping_view_is_malformed() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"].append("question")

    assert _codes(descriptor) == ["view-malformed"]


def test_invalid_surface_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"][0]["surface"] = "analysis"
    descriptor["views"][0]["route"] = "/analysis/research-question"

    assert _codes(descriptor) == ["view-surface-invalid"]


def test_invalid_id_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"][0]["id"] = "ResearchQuestion"

    assert _codes(descriptor) == ["view-id-invalid"]


def test_route_mismatch_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"][0]["route"] = "/explore/research_question"

    errors = descriptor_errors(descriptor)
    assert [error.code for error in errors] == ["view-route-mismatch"]
    assert "/explore/research-question" in errors[0].message


def test_missing_entity_types_is_reported() -> None:
    descriptor = _valid_descriptor()
    del descriptor["views"][0]["entity_types"]

    assert _codes(descriptor) == ["view-entity-types-missing"]


def test_empty_entity_types_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"][0]["entity_types"] = []

    assert _codes(descriptor) == ["view-entity-types-missing"]


def test_non_string_entity_types_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"][0]["entity_types"] = ["research_question", 7]

    assert _codes(descriptor) == ["view-entity-types-missing"]


def test_duplicate_visible_view_id_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["views"].append(
        {
            "id": "research_question",
            "label": "Duplicate",
            "surface": "explore",
            "entity_types": ["duplicate_kind"],
            "route": "/explore/research-question",
            "order": 600,
            "modules": [],
        }
    )

    errors = descriptor_errors(descriptor)
    assert [error.code for error in errors] == ["view-malformed"]
    assert errors[0].identity == "research_question"


def test_two_malformed_views_sharing_an_id_are_both_reported() -> None:
    # Identity is canonical content, not the ID, so neither error is deduplicated away.
    descriptor = _valid_descriptor()
    descriptor["views"] = [
        {"id": "question", "surface": "analysis", "entity_types": ["question"], "route": "/x"},
        {"id": "question", "surface": "references", "entity_types": ["question"], "route": "/y"},
    ]

    errors = [error for error in descriptor_errors(descriptor) if error.code == "view-surface-invalid"]
    assert len(errors) == 2
    assert len({error.identity for error in errors}) == 2


def test_non_array_hidden_kinds_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["hidden_kinds"] = {"entity_type": "talk"}

    errors = descriptor_errors(descriptor)
    assert [error.code for error in errors] == ["hidden-kinds-malformed"]
    assert errors[0].identity is None


def test_duplicate_hidden_entity_type_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["hidden_kinds"].append(
        {"entity_type": "talk", "entity_count": 1, "reason": "declared_hidden"}
    )

    errors = descriptor_errors(descriptor)
    assert [error.code for error in errors] == ["hidden-kinds-malformed"]
    assert errors[0].identity == "talk"


@pytest.mark.parametrize("reason", ["hidden", "", None, "FALLBACK_HIDDEN"])
def test_invalid_hidden_reason_is_reported(reason: object) -> None:
    descriptor = _valid_descriptor()
    descriptor["hidden_kinds"][0]["reason"] = reason

    assert _codes(descriptor) == ["hidden-kinds-malformed"]


@pytest.mark.parametrize("count", [-1, 1.5, "3", None, True])
def test_invalid_hidden_entity_count_is_reported(count: object) -> None:
    descriptor = _valid_descriptor()
    descriptor["hidden_kinds"][0]["entity_count"] = count

    assert _codes(descriptor) == ["hidden-kinds-malformed"]


def test_zero_hidden_entity_count_is_valid() -> None:
    descriptor = _valid_descriptor()
    descriptor["hidden_kinds"][0]["entity_count"] = 0

    assert descriptor_errors(descriptor) == []


def test_non_mapping_hidden_entry_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["hidden_kinds"].append("talk")

    assert _codes(descriptor) == ["hidden-kinds-malformed"]


def test_kind_visible_and_hidden_is_reported() -> None:
    descriptor = _valid_descriptor()
    descriptor["hidden_kinds"].append(
        {"entity_type": "research_question", "entity_count": 2, "reason": "declared_hidden"}
    )

    errors = descriptor_errors(descriptor)
    assert [error.code for error in errors] == ["kind-visible-and-hidden"]
    assert errors[0].identity == "research_question"


def test_all_structural_errors_aggregate() -> None:
    descriptor = {
        "views": [
            {
                "id": "Bad_Id",
                "surface": "analysis",
                "entity_types": [],
                "route": "/analysis/bad",
            },
            "not a mapping",
        ],
        "hidden_kinds": [{"entity_type": "talk", "entity_count": -1, "reason": "nope"}],
    }

    assert _codes(descriptor) == [
        "hidden-kinds-malformed",
        "hidden-kinds-malformed",
        "view-entity-types-missing",
        "view-id-invalid",
        "view-malformed",
        "view-surface-invalid",
    ]


def test_descriptor_error_is_frozen() -> None:
    error = DescriptorError(code="view-malformed", field="views[0]", message="bad", identity=None)

    with pytest.raises(AttributeError):
        error.code = "other"  # type: ignore[misc]

from __future__ import annotations

from science_tool.validate.checks.labnote_export import evaluate_labnote_export_views
from science_tool.validate.result import Severity


def test_labnote_export_view_missing_entity_types_is_error() -> None:
    results = list(
        evaluate_labnote_export_views(
            {
                "views": [
                    {
                        "id": "proposition",
                        "label": "Propositions",
                        "surface": "findings",
                        "route": "/findings/proposition",
                    }
                ]
            },
            "views.json",
        )
    )

    assert [(result.severity, result.rule_id) for result in results] == [
        (Severity.ERROR, "labnote-export.view-entity-types-missing")
    ]
    assert "proposition" in results[0].message


def test_labnote_export_view_declared_entity_types_is_clean() -> None:
    assert (
        list(
            evaluate_labnote_export_views(
                {
                    "views": [
                        {
                            "id": "proposition",
                            "label": "Propositions",
                            "surface": "findings",
                            "route": "/findings/proposition",
                            "entity_types": ["proposition"],
                        }
                    ]
                },
                "views.json",
            )
        )
        == []
    )


def test_labnote_export_check_is_registered() -> None:
    import sys

    import science_tool.validate.checks as checks

    module_name = "science_tool.validate.checks.labnote_export"
    original_entries = list(checks.CANONICAL_CHECKS)
    original_module = sys.modules.get(module_name)
    try:
        checks.clear_checks_for_tests()
        sys.modules.pop(module_name, None)
        checks._load_canonical_checks()

        assert any(entry.fn.__name__ == "check_labnote_export" for entry in checks.CANONICAL_CHECKS)
    finally:
        checks.CANONICAL_CHECKS[:] = original_entries
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module


def _view(**overrides) -> dict:
    view = {
        "id": "research_question",
        "label": "Research Questions",
        "surface": "explore",
        "route": "/explore/research-question",
        "entity_types": ["research_question"],
        "order": 500,
        "modules": [],
    }
    view.update(overrides)
    return view


def _rule_ids(document: dict) -> list[str]:
    return sorted(result.rule_id for result in evaluate_labnote_export_views(document, "views.json"))


def test_valid_single_and_multi_kind_views_are_clean() -> None:
    document = {
        "views": [
            _view(),
            _view(
                id="question",
                route="/explore/question",
                entity_types=["question", "inquiry"],
            ),
            _view(id="mechanism", surface="findings", route="/findings/mechanism", entity_types=["mechanism"]),
        ],
        "hidden_kinds": [{"entity_type": "talk", "entity_count": 3, "reason": "fallback_hidden"}],
    }

    assert list(evaluate_labnote_export_views(document, "views.json")) == []


def test_invalid_surface_is_reported_not_skipped() -> None:
    # The previous check silently ignored any surface it did not recognize.
    document = {"views": [_view(surface="analysis", route="/analysis/research-question")]}

    assert _rule_ids(document) == ["labnote-export.view-surface-invalid"]


def test_invalid_view_id_is_reported() -> None:
    document = {"views": [_view(id="ResearchQuestion")]}

    assert _rule_ids(document) == ["labnote-export.view-id-invalid"]


def test_underscore_route_is_a_mismatch() -> None:
    document = {"views": [_view(route="/explore/research_question")]}

    results = list(evaluate_labnote_export_views(document, "views.json"))
    assert [result.rule_id for result in results] == ["labnote-export.view-route-mismatch"]
    assert "/explore/research-question" in results[0].message


def test_malformed_hidden_inventory_is_reported() -> None:
    document = {
        "views": [_view()],
        "hidden_kinds": [{"entity_type": "talk", "entity_count": -1, "reason": "nope"}],
    }

    assert _rule_ids(document) == [
        "labnote-export.hidden-kinds-malformed",
        "labnote-export.hidden-kinds-malformed",
    ]


def test_duplicate_hidden_entity_type_is_reported() -> None:
    document = {
        "views": [_view()],
        "hidden_kinds": [
            {"entity_type": "talk", "entity_count": 1, "reason": "fallback_hidden"},
            {"entity_type": "talk", "entity_count": 2, "reason": "declared_hidden"},
        ],
    }

    assert _rule_ids(document) == ["labnote-export.hidden-kinds-malformed"]


def test_kind_visible_and_hidden_is_reported() -> None:
    document = {
        "views": [_view()],
        "hidden_kinds": [
            {"entity_type": "research_question", "entity_count": 1, "reason": "declared_hidden"}
        ],
    }

    assert _rule_ids(document) == ["labnote-export.kind-visible-and-hidden"]


def test_multiple_descriptor_problems_aggregate() -> None:
    document = {
        "views": [
            _view(id="Bad", surface="analysis", entity_types=[]),
            "not a mapping",
        ],
        "hidden_kinds": [{"entity_type": "talk", "entity_count": 1, "reason": "bogus"}],
    }

    assert _rule_ids(document) == [
        "labnote-export.hidden-kinds-malformed",
        "labnote-export.view-entity-types-missing",
        "labnote-export.view-id-invalid",
        "labnote-export.view-malformed",
        "labnote-export.view-surface-invalid",
    ]


def test_two_malformed_views_sharing_an_id_are_not_deduplicated() -> None:
    document = {
        "views": [
            _view(id="question", surface="analysis", route="/analysis/question"),
            _view(id="question", surface="references", route="/references/question"),
        ]
    }

    surface_results = [
        result
        for result in evaluate_labnote_export_views(document, "views.json")
        if result.rule_id == "labnote-export.view-surface-invalid"
    ]
    assert len(surface_results) == 2

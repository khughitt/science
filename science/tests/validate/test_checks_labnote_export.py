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

    assert [(result.severity, result.rule) for result in results] == [
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

    checks.clear_checks_for_tests()
    sys.modules.pop("science_tool.validate.checks.labnote_export", None)
    checks._load_canonical_checks()

    assert any(entry.fn.__name__ == "check_labnote_export" for entry in checks.CANONICAL_CHECKS)

from __future__ import annotations

from pathlib import Path

import pytest


def test_context_sources_raises_without_sources() -> None:
    from science_tool.graph.health_checks.base import HealthContext, context_sources

    context = HealthContext(project_root=Path("/tmp"))
    with pytest.raises(RuntimeError, match="health check requires loaded project sources"):
        context_sources(context)


def test_health_module_reuses_the_base_types() -> None:
    """health.py must not define its own copies of the shared machinery."""
    from science_tool.graph import health
    from science_tool.graph.health_checks import base

    assert health.HealthContext is base.HealthContext
    assert health.HealthCheck is base.HealthCheck


def test_identity_reference_fields_is_shared() -> None:
    """Two checks read this constant; it lives in exactly one place."""
    from science_tool.graph.health_checks.base import IDENTITY_REFERENCE_FIELDS

    assert "related" in IDENTITY_REFERENCE_FIELDS
    assert "source_refs" in IDENTITY_REFERENCE_FIELDS


def test_project_sources_empty_constants_are_shared() -> None:
    """Three checks return this unwired code/reason pair; it lives in exactly one place."""
    from science_tool.graph.health_checks.base import NO_ENTITIES_REASON, PROJECT_SOURCES_EMPTY

    assert PROJECT_SOURCES_EMPTY == "project_sources_empty"
    assert NO_ENTITIES_REASON == "project sources loaded zero entities; nothing was scanned"


def test_every_check_supplies_an_empty_state() -> None:
    """The registry carries each check's zero-value, so it is the only name list."""
    from science_tool.graph.health import HEALTH_CHECKS

    for check in HEALTH_CHECKS:
        assert callable(check.empty), f"{check.name} has no empty-state callable"


def _empty_prose_epistemics_expected() -> dict[str, object]:
    """Transcribed from health.py's `_empty_prose_epistemics()` literal."""
    return {
        "applicable": False,
        "summary": {},
        "coverage": {},
        "sources": [],
        "findings": [],
    }


def test_empty_check_results_payload_is_unchanged() -> None:
    """Characterization: pins the exact empty report across the registry refactor.

    Values transcribed from health.py's `_empty_check_results` dict literal as it
    stood before Phase 5. A diff here is a `health --format json` byte change.
    """
    from science_tool.graph.health import _empty_check_results

    assert _empty_check_results(Path("/tmp/project")) == {
        "identity_policy": [],
        "entity_identity": [],
        "layered_claim_migration": {
            "project_root": "/tmp/project",
            "rows": [],
            "summary": {
                "proposition_count": 0,
                "authored_claim_layer_count": 0,
                "authored_identification_strength_count": 0,
                "warning_count": 0,
                "todo_count": 0,
            },
        },
        "cross_paper_evidence": {
            "status": "ok",
            "empty_state": "no_propositions",
            "summary": {
                "propositions": 0,
                "propositions_with_units": 0,
                "units": 0,
                "faults": 0,
                "faults_by_reason": {},
                "contested": 0,
            },
            "findings": [],
            "propositions": [],
        },
        "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
        "managed_artifacts": [],
        "tooling_scaffold": [],
        "validate": [],
        "unresolved_refs": [],
        "unregistered_ref_kinds": [],
        "lingering_tags": [],
        "agent_context": [],
        "dataset_anomalies": [],
        "legacy_task_type": [],
        "invalid_entity_aspects": [],
        "prose_epistemics": _empty_prose_epistemics_expected(),
    }

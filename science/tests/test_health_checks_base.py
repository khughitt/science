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

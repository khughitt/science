"""Theme-kind discovery tests covering the eligibility filter."""

from __future__ import annotations

import logging
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_theme_discover_only_cross_project_themes_are_candidates(monkeypatch, caplog) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    _resolver(monkeypatch)
    caplog.set_level(logging.DEBUG, logger="science_tool.commons.promote")
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)

    slugs = set(result.candidates_by_slug)
    assert "cross-no-conflict" in slugs
    assert "cross-conflict" in slugs
    assert "cross-biological" in slugs
    assert "project-scope" not in slugs

    failed_names = [Path(fc.source_path).stem for fc in result.failed_candidates]
    assert "project-scope" not in failed_names


def test_theme_discover_malformed_scope_is_failed_candidate(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)

    failed_names = [Path(fc.source_path).stem for fc in result.failed_candidates]
    assert "malformed-scope" in failed_names


def test_theme_discover_groups_shared_themes(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_THEME)

    assert len(result.candidates_by_slug["cross-no-conflict"]) == 2
    assert len(result.candidates_by_slug["cross-conflict"]) == 2

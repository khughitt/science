"""Theme-kind plan tests, including the biological validation failure."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_theme_plan_happy_path_canonical_keeps_kind_and_scope(tmp_path, monkeypatch) -> None:
    """Canonical theme retains theme_kind + theme_scope. Overlay strips both
    (overlay-1.1 doesn't allow them)."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_THEME)
    discovery = type(discovery)(
        candidates_by_slug={
            "cross-no-conflict": discovery.candidates_by_slug["cross-no-conflict"]
        },
        failed_candidates=[],
    )

    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_THEME)

    d = next(d for d in plan.decisions if d.slug == "cross-no-conflict")
    assert "theme_kind: methodological" in d.canonical_content
    assert "theme_scope: cross-project" in d.canonical_content
    for overlay in d.overlays.values():
        assert "theme_kind:" not in overlay.after_content
        assert "theme_scope:" not in overlay.after_content


def test_theme_plan_biological_fails_validation(tmp_path, monkeypatch) -> None:
    """A cross-project theme with theme_kind: biological is eligible at
    discovery but fails plan-time validation (the enum doesn't include
    biological)."""
    from science_tool.commons.errors import PromoteValidationError
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)
    discovery = type(discovery)(
        candidates_by_slug={
            "cross-biological": discovery.candidates_by_slug["cross-biological"]
        },
        failed_candidates=[],
    )

    with pytest.raises(PromoteValidationError) as exc_info:
        plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_THEME)
    err = exc_info.value
    assert err.decision_slug == "cross-biological"
    assert err.target_kind == "canonical"
    assert "biological" in err.schema_message or "theme_kind" in err.schema_message

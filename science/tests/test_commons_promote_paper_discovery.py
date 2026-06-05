"""Paper-kind discovery integration tests using the fixture corpus."""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_paper_discover_walks_background_papers(monkeypatch) -> None:
    """Discovery walks both entities/papers/ and doc/background/papers/."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_PAPER)

    slugs = set(result.candidates_by_slug)
    assert "adams2025" in slugs
    assert "flint2026" in slugs


def test_paper_background_candidate_carries_original_path(monkeypatch) -> None:
    """Background-papers candidates keep their original source path for apply."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_PAPER)

    candidates = result.candidates_by_slug["flint2026"]
    assert len(candidates) == 1
    assert "background/papers" in str(candidates[0].overlay_source_path)

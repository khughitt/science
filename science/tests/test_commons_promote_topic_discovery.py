"""Topic-kind discovery integration tests using the fixture corpus."""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_topic_discover_single_project_finds_single_instance(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    slugs = set(result.candidates_by_slug)
    assert "single-instance" in slugs
    assert "shared-no-conflict" in slugs
    assert "shared-conflict" in slugs
    assert "flatten-source" not in slugs
    assert "collide" in slugs


def test_topic_discover_doc_topic_collision_is_ignored(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    assert "collide" in result.candidates_by_slug
    assert not [fc for fc in result.failed_candidates if "collide" in fc.error_message]


def test_topic_discover_two_projects_groups_shared_slugs(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)

    assert len(result.candidates_by_slug["shared-no-conflict"]) == 2
    assert len(result.candidates_by_slug["shared-conflict"]) == 2


def test_topic_discover_ignores_background_topic_sources(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    assert "flatten-source" not in result.candidates_by_slug

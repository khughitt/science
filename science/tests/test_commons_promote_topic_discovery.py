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
    assert "flatten-source" in slugs
    assert "collide" not in slugs


def test_topic_discover_collide_records_failed_candidate(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    collide_failures = [
        fc for fc in result.failed_candidates if "collide" in fc.error_message
    ]
    assert len(collide_failures) >= 1
    assert "both" in collide_failures[0].error_message.lower()


def test_topic_discover_two_projects_groups_shared_slugs(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)

    assert len(result.candidates_by_slug["shared-no-conflict"]) == 2
    assert len(result.candidates_by_slug["shared-conflict"]) == 2


def test_topic_discover_flatten_source_carries_original_path(monkeypatch) -> None:
    """Background-topic candidates keep their original source path for apply."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    candidates = result.candidates_by_slug["flatten-source"]
    assert len(candidates) == 1
    assert "background/topics" in str(candidates[0].overlay_source_path)

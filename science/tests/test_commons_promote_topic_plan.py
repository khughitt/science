"""Topic-kind plan integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def _only_slugs(discovery, *slugs):
    from science_tool.commons.promote import DiscoveryResult

    return DiscoveryResult(
        candidates_by_slug={
            slug: discovery.candidates_by_slug[slug]
            for slug in slugs
        },
        failed_candidates=discovery.failed_candidates,
    )


def test_topic_plan_single_instance_no_prompt(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)
    discovery = _only_slugs(discovery, "single-instance")
    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_TOPIC)

    by_slug = {d.slug: d for d in plan.decisions}
    assert "single-instance" in by_slug
    canonical_content = by_slug["single-instance"].canonical_artifacts[0].content
    assert "id: topic:single-instance" in canonical_content
    assert "kind: topic" in canonical_content


def test_topic_plan_shared_no_conflict_unifies_canonical(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)
    discovery = _only_slugs(discovery, "shared-no-conflict")
    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_TOPIC)

    by_slug = {d.slug: d for d in plan.decisions}
    d = by_slug["shared-no-conflict"]
    assert len(d.overlays) == 2
    assert "## Relevance to This Project" not in d.canonical_artifacts[0].content
    for slug in ("proj-alpha", "proj-beta"):
        assert "Relevance to This Project" in d.overlays[slug].after_content


def test_topic_plan_conflict_uses_prompt_resolve(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)

    captured = []

    def stub(conflict):
        captured.append((conflict.slug, conflict.field))
        return conflict.candidates["proj-alpha"]

    plan = plan_promote(
        discovery,
        commons_root=tmp_path,
        kind=PROMOTE_KIND_TOPIC,
        resolve_conflict=stub,
    )
    assert ("shared-conflict", "title") in captured
    by_slug = {d.slug: d for d in plan.decisions}
    assert "Title from alpha" in by_slug["shared-conflict"].canonical_artifacts[0].content


def test_topic_plan_aborts_on_user_abort(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteConflictAbort
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)

    def abort(_c):
        raise PromoteConflictAbort("test")

    with pytest.raises(PromoteConflictAbort):
        plan_promote(
            discovery,
            commons_root=tmp_path,
            kind=PROMOTE_KIND_TOPIC,
            resolve_conflict=abort,
        )

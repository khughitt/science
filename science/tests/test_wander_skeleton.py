from __future__ import annotations

import json
from datetime import date

import yaml

from science_tool.wander.context import ContextBundle
from science_tool.wander.neighbors import NeighborEdge, NeighborSet
from science_tool.wander.references import Reference
from science_tool.wander.skeleton import render_json, render_markdown_skeleton
from science_tool.wander.stub_smell import compute_stub_signals


def _bundle(entity_id: str = "hypothesis:h1", **overrides) -> ContextBundle:
    base = dict(
        entity_id=entity_id,
        uri=f"https://example.org/{entity_id.replace(':', '/')}",
        kind=entity_id.split(":")[0],
        label="Sample label",
        freshness_state="fresh",
        weight=1.25,
        components={"incoming_bears_on": 0.0, "days_since_last_review": 30.0},
        source_path="doc/h1.md",
        mtime=date(2026, 4, 1),
        content_length=412,
        created_date=date(2026, 1, 1),
        neighbors=NeighborSet(other_outgoing=[NeighborEdge("relatedTo", "hypothesis:h2", "u")]),
        active_references=[Reference(entity_id="task:t1", kind="task")],
    )
    base.update(overrides)
    return ContextBundle(**base)


def test_markdown_skeleton_has_required_sections_and_frontmatter() -> None:
    bundles = [_bundle("hypothesis:h1"), _bundle("hypothesis:h2"), _bundle("proposition:p1")]
    today = date(2026, 5, 9)
    bundles_with_signals = [(b, compute_stub_signals(b, today=today)) for b in bundles]

    text = render_markdown_skeleton(
        walk_id="2026-05-09-1430",
        walk_date=today,
        seed=42,
        n=3,
        bundles_with_signals=bundles_with_signals,
    )

    parts = text.split("---\n", 2)
    assert parts[0] == ""
    frontmatter = yaml.safe_load(parts[1])
    assert frontmatter["walk_id"] == "2026-05-09-1430"
    assert frontmatter["seed"] == 42
    assert frontmatter["n"] == 3
    assert frontmatter["sampled"] == ["hypothesis:h1", "hypothesis:h2", "proposition:p1"]

    body = parts[2]
    for heading in (
        "## Sample",
        "## Per-entity review",
        "## Pairwise connections",
        "## Prune candidates",
        "## Spawned tasks",
    ):
        assert heading in body
    assert body.count("### hypothesis:h1 ↔ hypothesis:h2") == 1
    assert body.count("### hypothesis:h1 ↔ proposition:p1") == 1
    assert body.count("### hypothesis:h2 ↔ proposition:p1") == 1
    assert "stub-smell signals" in body.lower()


def test_json_serialization_round_trips_bundle_fields() -> None:
    bundle = _bundle()
    today = date(2026, 5, 9)
    payload = render_json(
        walk_id="2026-05-09-1430",
        walk_date=today,
        seed=42,
        n=1,
        bundles_with_signals=[(bundle, compute_stub_signals(bundle, today=today))],
    )

    parsed = json.loads(payload)
    assert parsed["walk_id"] == "2026-05-09-1430"
    assert parsed["bundles"][0]["entity_id"] == "hypothesis:h1"
    assert parsed["bundles"][0]["stub_signals"]["is_stub_candidate"] is False

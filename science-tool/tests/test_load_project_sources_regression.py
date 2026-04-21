"""Snapshot-based regression test for load_project_sources.

The snapshot uses a projection that excludes the new `provider` and `description`
fields (added in steps 7-8 of the multi-backend-entity-resolver plan). This lets
the regression assertion stay byte-identical across every commit in the plan,
even when those fields are intentionally added.
"""
from __future__ import annotations

import json
from pathlib import Path

from science_tool.graph.sources import load_project_sources


FIXTURE = Path(__file__).parent / "fixtures" / "spec_y_kitchen_sink"
SNAPSHOT = Path(__file__).parent / "fixtures" / "spec_y_kitchen_sink" / "snapshot.json"


def _project_for_snapshot(entities: list) -> list[dict]:
    """Drop fields the spec adds incrementally; the snapshot stays stable across commits."""
    excluded = {"provider", "description"}
    projected: list[dict] = []
    for e in entities:
        d = e.model_dump()
        projected.append({k: v for k, v in d.items() if k not in excluded})
    # Sort by canonical_id for deterministic ordering.
    projected.sort(key=lambda d: d.get("canonical_id", ""))
    return projected


def test_load_project_sources_kitchen_sink_snapshot() -> None:
    sources = load_project_sources(FIXTURE)
    actual = _project_for_snapshot(sources.entities)
    expected = json.loads(SNAPSHOT.read_text())
    assert actual == expected, (
        f"Snapshot regression: load_project_sources output diverged.\n"
        f"To inspect: diff <(echo '{json.dumps(actual, indent=2)}') {SNAPSHOT}\n"
        f"If the diff is intentional, regenerate via:\n"
        f"  python -c 'import json; from pathlib import Path; "
        f"from science_tool.graph.sources import load_project_sources; "
        f"from tests.test_load_project_sources_regression import _project_for_snapshot, FIXTURE, SNAPSHOT; "
        f"SNAPSHOT.write_text(json.dumps(_project_for_snapshot(load_project_sources(FIXTURE).entities), indent=2) + chr(10))'"
    )

"""Snapshot-based regression test for load_project_sources.

Post-cutover: entities are typed Entity/ProjectEntity subclasses. The snapshot
serializes them with `mode='json'` so date/enum values survive round-tripping.

The projection excludes fields that were on the old Spec Y SourceEntity but do
not exist on the unified Entity family (`provider`, `description`). It also
excludes a handful of Entity-only fields that only matter for typed subclass
invariants (`accessions`, `consumed_by`, `local_path`, `siblings`, `derivation`,
`access`, `datapackage`, `parent_dataset`, `datasets`, `maturity`, `rival_model_packet_ref`,
`created`, `updated`, `pre_registered`, `pre_registered_date`, `sync_source`) so
the snapshot stays focused on the load-path fields this regression cares about.
"""

from __future__ import annotations

import json
from pathlib import Path

from science_tool.graph.sources import load_project_sources


FIXTURE = Path(__file__).parent / "fixtures" / "spec_y_kitchen_sink"
SNAPSHOT = Path(__file__).parent / "fixtures" / "spec_y_kitchen_sink" / "snapshot.json"


_EXCLUDED_FIELDS = frozenset(
    {
        # Spec Y fields removed from Entity hierarchy:
        "provider",
        "description",
        # Entity fields not relevant to this regression:
        "accessions",
        "consumed_by",
        "local_path",
        "siblings",
        "derivation",
        "access",
        "datapackage",
        "parent_dataset",
        "datasets",
        "maturity",
        "rival_model_packet_ref",
        "created",
        "updated",
        "pre_registered",
        "pre_registered_date",
        "sync_source",
        "id",  # duplicate of canonical_id after normalization
        "content",  # full body; content_preview is what we snapshot
    }
)


def _project_for_snapshot(entities: list) -> list[dict]:
    """Project to a stable subset of fields. mode='json' is required for dates/enums."""
    projected: list[dict] = []
    for e in entities:
        d = e.model_dump(mode="json")
        projected.append({k: v for k, v in d.items() if k not in _EXCLUDED_FIELDS})
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

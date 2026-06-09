from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"

_LOCAL_MANIFEST_WITH_DECISION = (
    "name: demo-local\n"
    "imports:\n"
    "  - core\n"
    "strictness: typed-extension\n"
    "entity_kinds:\n"
    "  - name: decision\n"
    "    canonical_prefix: decision\n"
    "    layer: layer/local\n"
    "    description: Project-local design decision.\n"
    "relation_kinds: []\n"
)


def test_classified_row_carries_path_and_line(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    # Declare the `decision` local kind so the graph loader emits rows for it.
    # Without this manifest entry, decision rows are skipped pre-triage because
    # `decision` is not a graph-core kind.
    (agg / "manifest.yaml").write_text(_LOCAL_MANIFEST_WITH_DECISION, encoding="utf-8")
    (agg / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "concept:a",
                        "kind": "concept",
                        "title": "A",
                        "source_path": "knowledge/sources/local/entities.yaml",
                    },
                    {
                        "canonical_id": "concept:b",
                        "kind": "concept",
                        "title": "B",
                        "source_path": "knowledge/sources/local/entities.yaml",
                    },
                    {
                        "canonical_id": "decision:d1",
                        "kind": "decision",
                        "title": "D1",
                        # source_path deliberately differs from the aggregate file path.
                        # This proves that .path is wired from the declaring aggregate
                        # file, not from the entity's source_path provenance pointer.
                        "source_path": "core/decisions.md",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = {t.canonical_id: t for t in classify_aggregate_rows(sources)}
    assert rows["concept:a"].path == "knowledge/sources/local/entities.yaml"
    assert rows["concept:b"].path == "knowledge/sources/local/entities.yaml"
    # Distinct rows have distinct line indices; both are non-None ints.
    assert isinstance(rows["concept:a"].line, int)
    assert isinstance(rows["concept:b"].line, int)
    assert rows["concept:a"].line != rows["concept:b"].line
    # Prove that .path locates the DECLARING aggregate file, not the entity's
    # source_path provenance pointer.  If path were mis-wired from source_path,
    # this block would fail because source_path is "core/decisions.md".
    assert rows["decision:d1"].path == "knowledge/sources/local/entities.yaml"  # locates the declaring file
    assert rows["decision:d1"].source_path == "core/decisions.md"  # provenance pointer is distinct
    assert rows["decision:d1"].path != rows["decision:d1"].source_path

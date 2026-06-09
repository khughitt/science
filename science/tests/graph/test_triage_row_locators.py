from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"


def test_classified_row_carries_path_and_line(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = tmp_path / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
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

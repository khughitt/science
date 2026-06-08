from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo-project\nprofile: research\nprofiles: {local: local}\n"


def _write_project(root: Path, entries: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    agg = root / "knowledge" / "sources" / "local"
    agg.mkdir(parents=True, exist_ok=True)
    (agg / "entities.yaml").write_text(yaml.safe_dump({"entities": entries}), encoding="utf-8")


def _write_dataset_md(root: Path, slug: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(
        f'---\nid: "{ident}"\ntype: "dataset"\ntitle: "{ident}"\n'
        'origin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


def test_aggregate_rows_capture_lone_and_shadowed(tmp_path: Path) -> None:
    # The shadowed dataset's Entity is deduped away under non-strict load, but its
    # aggregate row metadata must STILL be captured (the High-finding fix).
    _write_dataset_md(tmp_path, "shadowed", "dataset:shadowed")
    _write_project(
        tmp_path,
        [
            {
                "canonical_id": "concept:coined",
                "kind": "concept",
                "title": "Coined",
                "source_path": "knowledge/sources/local/entities.yaml",
            },
            {
                "canonical_id": "dataset:shadowed",
                "kind": "dataset",
                "title": "Shadowed",
                "origin": "external",
                "access": {"level": "public", "verified": False},
                "source_path": "knowledge/sources/local/entities.yaml",
            },
        ],
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    by_id = {m.canonical_id: m for m in sources.aggregate_rows}
    assert set(by_id) == {"concept:coined", "dataset:shadowed"}
    assert by_id["concept:coined"].kind == "concept"
    assert by_id["concept:coined"].source_path == "knowledge/sources/local/entities.yaml"
    assert by_id["concept:coined"].path == "knowledge/sources/local/entities.yaml"
    assert by_id["dataset:shadowed"].line is not None


def test_non_string_source_path_normalized_to_none(tmp_path: Path) -> None:
    # source_path is extra metadata the entity schema ignores, so a malformed
    # (non-string) value survives into `raw`. Normalize it to None at capture so the
    # read-only report cannot crash on `.startswith()` downstream.
    _write_project(
        tmp_path,
        [{"canonical_id": "concept:weird", "kind": "concept", "title": "Weird", "source_path": 123}],
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    by_id = {m.canonical_id: m for m in sources.aggregate_rows}
    assert by_id["concept:weird"].source_path is None

"""End-to-end migration scenarios: mixed-mode coexistence, collision detection, recovery."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.source_types import EntityIdCollisionError


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: mig\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def test_mid_migration_mixed_mode(tmp_path: Path) -> None:
    """3 datasets in markdown + 2 as datapackage-directory both load. No collision."""
    _seed(tmp_path)
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    for slug in ("ds-md-1", "ds-md-2", "ds-md-3"):
        (tmp_path / "doc" / "datasets" / f"{slug}.md").write_text(
            f'---\nid: "dataset:{slug}"\ntype: "dataset"\ntitle: "{slug}"\norigin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
            encoding="utf-8",
        )
    for slug in ("ds-dp-1", "ds-dp-2"):
        dp_dir = tmp_path / "data" / slug
        dp_dir.mkdir(parents=True)
        (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
            "profiles": ["science-pkg-entity-1.0"],
            "name": slug,
            "id": f"dataset:{slug}",
            "type": "dataset",
            "title": slug,
            "origin": "external",
            "access": {"level": "public", "verified": False},
            "resources": [{"name": "r", "path": "r.csv"}],
        }), encoding="utf-8")
    from science_tool.graph.sources import load_project_sources
    sources = load_project_sources(tmp_path)
    ids = {e.canonical_id for e in sources.entities}
    assert "dataset:ds-md-1" in ids
    assert "dataset:ds-md-2" in ids
    assert "dataset:ds-md-3" in ids
    assert "dataset:ds-dp-1" in ids
    assert "dataset:ds-dp-2" in ids


def test_bad_migration_collision_then_recovery(tmp_path: Path) -> None:
    """Markdown + datapackage-directory with same canonical_id raises; deleting markdown recovers."""
    _seed(tmp_path)
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    md = tmp_path / "doc" / "datasets" / "x.md"
    md.write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\norigin: "external"\naccess:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    dp_dir = tmp_path / "data" / "x"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(yaml.safe_dump({
        "profiles": ["science-pkg-entity-1.0"],
        "name": "x",
        "id": "dataset:x",
        "type": "dataset",
        "title": "X dp",
        "origin": "external",
        "access": {"level": "public", "verified": False},
        "resources": [{"name": "r", "path": "r.csv"}],
    }), encoding="utf-8")
    from science_tool.graph.sources import load_project_sources
    with pytest.raises(EntityIdCollisionError) as exc_info:
        load_project_sources(tmp_path)
    msg = str(exc_info.value)
    assert "dataset:x" in msg
    assert "doc/datasets/x.md" in msg
    assert "data/x/datapackage.yaml" in msg
    # Recovery: delete the markdown, re-run.
    md.unlink()
    sources = load_project_sources(tmp_path)
    es = [e for e in sources.entities if e.canonical_id == "dataset:x"]
    assert len(es) == 1
    assert es[0].provider == "datapackage-directory"

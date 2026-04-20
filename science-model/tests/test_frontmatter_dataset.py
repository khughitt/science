"""parse_entity_file extensions for dataset entities — back-compat + new shape."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from science_model.frontmatter import parse_entity_file


@pytest.fixture
def tmp_md(tmp_path: Path):
    def _write(content: str, name: str = "x.md") -> Path:
        p = tmp_path / "doc" / "datasets" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
        return p

    return _write


def test_legacy_flat_access_parses_as_access_level(tmp_md) -> None:
    p = tmp_md(
        """
        ---
        id: "dataset:legacy"
        type: "dataset"
        title: "Legacy"
        access: "public"
        datasets:
          - "EGAD00001"
        ---
        Body.
    """,
        name="legacy.md",
    )
    e = parse_entity_file(p, project_slug="testproj")
    assert e is not None
    assert e.origin == "external"  # default for legacy datasets
    assert e.access is not None
    assert e.access.level == "public"
    assert e.access.verified is False
    assert e.accessions == ["EGAD00001"]  # `datasets:` aliased


def test_new_shape_origin_external(tmp_md) -> None:
    p = tmp_md(
        """
        ---
        id: "dataset:new"
        type: "dataset"
        title: "New"
        profiles: ["science-pkg-entity-1.0"]
        origin: "external"
        tier: "use-now"
        access:
          level: "public"
          verified: true
          verification_method: "retrieved"
          last_reviewed: "2026-04-19"
          verified_by: "claude"
          source_url: "https://x"
        accessions: ["E1"]
        datapackage: "data/new/datapackage.yaml"
        ---
    """,
        name="new.md",
    )
    e = parse_entity_file(p, project_slug="testproj")
    assert e is not None
    assert e.origin == "external"
    assert e.access is not None and e.access.verified is True
    assert e.datapackage == "data/new/datapackage.yaml"

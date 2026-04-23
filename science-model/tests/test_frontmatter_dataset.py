"""parse_entity_file extensions for dataset entities — back-compat + new shape."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from science_model.entities import EntityType
from science_model.identity import EntityScope, ExternalId
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


def test_derived_frontmatter_parses(tmp_md) -> None:
    p = tmp_md(
        """
        ---
        id: "dataset:wf-r1-out1"
        type: "dataset"
        title: "Derived"
        profiles: ["science-pkg-entity-1.0"]
        origin: "derived"
        tier: "use-now"
        datapackage: "results/wf/r1/out1/datapackage.yaml"
        derivation:
          workflow: "workflow:wf"
          workflow_run: "workflow-run:wf-r1"
          git_commit: "abc"
          config_snapshot: "results/wf/r1/config.yaml"
          produced_at: "2026-04-19T12:00:00Z"
          inputs:
            - "dataset:upstream"
        consumed_by:
          - "plan:p1"
          - "research-package:rp1"
        ---
    """,
        name="der.md",
    )
    e = parse_entity_file(p, project_slug="testproj")
    assert e is not None
    assert e.origin == "derived"
    assert e.access is None
    assert e.derivation is not None
    assert e.derivation.workflow_run == "workflow-run:wf-r1"
    assert e.derivation.inputs == ["dataset:upstream"]
    assert "research-package:rp1" in e.consumed_by


def test_research_package_entity_parses(tmp_path: Path) -> None:
    """Entity-typed research-package entries parse without origin/access/derivation set."""
    p = tmp_path / "research" / "packages" / "lens" / "rp1" / "research-package.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        textwrap.dedent(
            """
        ---
        id: "research-package:rp1"
        type: "research-package"
        title: "RP1"
        displays: ["dataset:wf-r1-out1"]
        ---
    """
        ).lstrip("\n"),
        encoding="utf-8",
    )
    e = parse_entity_file(p, project_slug="testproj")
    assert e is not None
    assert e.type == EntityType.RESEARCH_PACKAGE
    assert e.origin is None
    assert e.access is None


def test_dataset_frontmatter_preserves_identity_metadata(tmp_md) -> None:
    p = tmp_md(
        """
        ---
        id: "dataset:identity-demo"
        type: "dataset"
        title: "Identity Demo"
        primary_external_id:
          source: "GEO"
          id: "GSE7039"
          curie: "GEO:GSE7039"
          provenance: "manual"
        xrefs:
          - source: "BioProject"
            id: "PRJNA12345"
            curie: "BioProject:PRJNA12345"
            provenance: "manual"
        scope: "shared"
        deprecated_ids: ["dataset:old-demo"]
        taxon: "NCBITaxon:9606"
        origin: "external"
        access: "public"
        ---
        Body.
    """,
        name="identity-demo.md",
    )
    e = parse_entity_file(p, project_slug="testproj")
    assert e is not None
    assert e.primary_external_id == ExternalId(
        source="GEO",
        id="GSE7039",
        curie="GEO:GSE7039",
        provenance="manual",
    )
    assert e.xrefs == [
        ExternalId(
            source="BioProject",
            id="PRJNA12345",
            curie="BioProject:PRJNA12345",
            provenance="manual",
        )
    ]
    assert e.scope == EntityScope.SHARED
    assert e.deprecated_ids == ["dataset:old-demo"]
    assert e.taxon == "NCBITaxon:9606"

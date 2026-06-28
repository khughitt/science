from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from science_tool.labnote_export import export_labnote_package


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(text).strip() + "\n", encoding="utf-8")


def write_minimal_project(root: Path) -> None:
    write_text(
        root / "science.yaml",
        """
        name: Post-Acute Infection Syndromes
        id: post-acute-infection
        last_modified: 2026-06-28
        labnote:
          label: PAIS
        """,
    )
    write_text(
        root / "papers" / "references.bib",
        """
        @article{Smith2020,
          author = {Smith, Jane and Doe, John},
          title = {Example immune persistence paper},
          journal = {Example Journal},
          year = {2020},
          doi = {10.1000/example}
        }
        """,
    )
    write_text(
        root / "entities" / "propositions" / "0001-example-proposition.md",
        """
        ---
        id: proposition:0001-example-proposition
        type: proposition
        title: Example proposition
        status: active
        confidence: supported
        sensitivity: public
        discusses:
          - frame: synthesis:0001-example-synthesis
            role: mechanism
        ---
        # Story

        This public proposition cites [@Smith2020].

        # Evidence

        Evidence prose is preserved as a second section.
        """,
    )
    write_text(
        root / "entities" / "synthesis" / "0001-example-synthesis.md",
        """
        ---
        id: synthesis:0001-example-synthesis
        type: synthesis
        title: Example synthesis
        status: active
        sensitivity: public
        ---
        Synthesis body text.
        """,
    )
    write_text(
        root / "entities" / "papers" / "internal-paper.md",
        """
        ---
        id: paper:internal-paper
        type: paper
        title: Internal paper
        sensitivity: internal
        ---
        This record must not enter the public package.
        """,
    )


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_export_labnote_package_writes_public_package_contract(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)

    project = read_json(out / "project.json")
    manifest = read_json(out / "manifest.json")
    views = read_json(out / "views.json")
    entities = read_json(out / "entities" / "index.json")
    prose = read_json(out / "prose_bundles" / "entity_prose_bundles.json")
    refs = read_json(out / "references" / "index.json")

    assert diagnostics["errors"] == []
    assert project["schema_version"] == "science-project-package.v1"
    assert project["project"]["id"] == "post-acute-infection"
    assert project["project"]["label"] == "PAIS"
    assert project["package"]["data_version"] == manifest["data_version"]
    assert manifest["data_version"].startswith("2026-06-28+")
    assert project["capabilities"] == {
        "entity_search": True,
        "findings": True,
        "graphs": False,
        "dataset_support": False,
        "quantitative_tables": False,
        "restricted_resources_present": True,
    }

    resource_by_name = {resource["name"]: resource for resource in manifest["resources"]}
    for name in (
        "project.json",
        "views.json",
        "references",
        "entities",
        "entity_prose",
        "entity_links",
        "export_diagnostics",
    ):
        assert name in resource_by_name
        resource = resource_by_name[name]
        assert resource["kind"] in {"bundle", "descriptor"}
        assert resource["sensitivity"] == "public"
        assert isinstance(resource["bytes"], int) and resource["bytes"] > 0
        assert len(resource["sha256"]) == 64
        assert resource["media_type"] == "application/json"

    exported_ids = {entity["id"] for entity in entities["entities"]}
    assert exported_ids == {
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
    }
    proposition = next(e for e in entities["entities"] if e["type"] == "proposition")
    assert proposition["class"] == "epistemic"
    assert proposition["display_name"] == "Example proposition"
    assert proposition["route"] is None
    assert proposition["source_path"] == "entities/propositions/0001-example-proposition.md"

    assert prose["contract"] == "science.entity_prose"
    assert prose["schema_version"] == "1"
    sections = prose["entities"]["proposition:0001-example-proposition"]["sections"]
    assert [section["key"] for section in sections] == ["story", "evidence"]
    assert "[@Smith2020]" in sections[0]["markdown"]

    assert refs["contract"] == "science.references"
    assert refs["schema_version"] == "1"
    assert "Smith2020" in refs["references"]

    view_ids = [view["id"] for view in views["views"]]
    assert view_ids == ["proposition", "synthesis"]
    assert views["views"][0]["surface"] == "findings"
    assert views["views"][0]["route"] == "/findings/proposition"


def test_export_labnote_package_fails_on_unresolved_public_citation(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("[@Smith2020]", "[@Missing2026]"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved citation"):
        export_labnote_package(project_root=project_root, out_dir=out)

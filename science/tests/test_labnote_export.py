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


def test_export_labnote_package_filters_non_public_access_levels(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "entities" / "datasets" / "controlled.md",
        """
        ---
        id: dataset:controlled
        type: dataset
        title: Controlled dataset
        access:
          level: controlled
        ---
        This dataset is not public.
        """,
    )

    export_labnote_package(project_root=project_root, out_dir=out)

    entities = read_json(out / "entities" / "index.json")
    exported_ids = {entity["id"] for entity in entities["entities"]}
    assert "dataset:controlled" not in exported_ids
    assert read_json(out / "project.json")["capabilities"]["restricted_resources_present"] is True


def test_export_labnote_package_data_version_changes_with_exported_frontmatter(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "pais"
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_minimal_project(project_root)

    export_labnote_package(project_root=project_root, out_dir=first)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("title: Example proposition", "title: Renamed proposition"),
        encoding="utf-8",
    )
    export_labnote_package(project_root=project_root, out_dir=second)

    assert read_json(first / "manifest.json")["data_version"] != read_json(second / "manifest.json")[
        "data_version"
    ]


def test_export_labnote_package_fails_on_unresolved_source_ref_citation(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "sensitivity: public",
            "sensitivity: public\nsource_refs:\n  - cite: Missing2026",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved source_refs citation"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_export_labnote_package_fails_on_unresolved_string_source_ref_citation(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "sensitivity: public",
            "sensitivity: public\nsource_refs:\n  - cite:Missing2026",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved source_refs citation"):
        export_labnote_package(project_root=project_root, out_dir=out)


def test_export_labnote_package_exports_frontmatter_links_and_diagnostics(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    proposition_path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    proposition_path.write_text(
        proposition_path.read_text(encoding="utf-8").replace(
            "discusses:\n  - frame: synthesis:0001-example-synthesis\n    role: mechanism",
            """discusses:
  - synthesis:0001-example-synthesis
  - frame: synthesis:0001-example-synthesis
    role: mechanism
  - frame: dataset:gse-example
    role: unclear_custom_role
related:
  - method:example-method
  - dataset:gse-example
  - paper:internal-paper
  - interpretation:not-exported
relations:
  - predicate: cito:supports
    target: dataset:gse-example""",
        ),
        encoding="utf-8",
    )
    write_text(
        project_root / "entities" / "datasets" / "gse-example.md",
        """
        ---
        id: dataset:gse-example
        type: dataset
        title: Example dataset
        sensitivity: public
        ---
        Dataset text.
        """,
    )
    write_text(
        project_root / "entities" / "methods" / "example-method.md",
        """
        ---
        id: method:example-method
        type: method
        title: Example method
        sensitivity: public
        ---
        Method text.
        """,
    )

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)
    links = read_json(out / "links" / "index.json")

    assert links["contract"] == "science.entity_links"
    assert links["schema_version"] == "1"
    rows = {
        (
            row["source"],
            row["target"],
            row["predicate"],
            row["link_role"],
            row["finding_backlink"],
        )
        for row in links["links"]
    }
    assert (
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
        "cito:discusses",
        "related",
        True,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
        "cito:discusses",
        "mechanism",
        True,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "method:example-method",
        "skos:related",
        "related",
        False,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "dataset:gse-example",
        "skos:related",
        "related",
        True,
    ) in rows
    assert (
        "proposition:0001-example-proposition",
        "dataset:gse-example",
        "cito:supports",
        "supports",
        True,
    ) in rows
    assert all(row["target"] != "paper:internal-paper" for row in links["links"])
    assert not any("paper:internal-paper" in warning["message"] for warning in diagnostics["warnings"])
    assert any(
        warning["message"] == "link target omitted because it is not exported"
        for warning in diagnostics["warnings"]
    )
    assert any("interpretation:not-exported" in warning["message"] for warning in diagnostics["warnings"])
    assert any("unclear_custom_role" in warning["message"] for warning in diagnostics["warnings"])


def test_export_labnote_package_warns_and_omits_links_to_unknown_entities(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    path = project_root / "entities" / "propositions" / "0001-example-proposition.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "discusses:",
            "related:\n  - dataset:missing\ndiscusses:",
        ),
        encoding="utf-8",
    )

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)
    links = read_json(out / "links" / "index.json")

    assert all(row["target"] != "dataset:missing" for row in links["links"])
    assert any("dataset:missing" in warning["message"] for warning in diagnostics["warnings"])


def test_export_labnote_package_exports_knowledge_graph_links(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)
    write_text(
        project_root / "knowledge" / "graph.trig",
        """
        @prefix cito: <http://purl.org/spar/cito/> .
        @prefix sci: <http://example.org/science/vocab/> .

        <http://example.org/project/graph/knowledge> {
          <http://example.org/project/proposition/0001-example-proposition>
            cito:supports
            <http://example.org/project/synthesis/0001-example-synthesis> .
          <http://example.org/project/proposition/0001-example-proposition>
            sci:synthesizes
            <http://example.org/project/synthesis/0001-example-synthesis> .
          <http://example.org/project/proposition/0001-example-proposition>
            sci:implements
            <http://example.org/project/synthesis/0001-example-synthesis> .
          <http://example.org/project/interpretation/not-exported>
            sci:synthesizes
            <http://example.org/project/synthesis/0001-example-synthesis> .
        }
        """,
    )

    diagnostics = export_labnote_package(project_root=project_root, out_dir=out)
    links = read_json(out / "links" / "index.json")

    rows = {
        (
            row["source"],
            row["target"],
            row["predicate"],
            row["link_role"],
            row["finding_backlink"],
        )
        for row in links["links"]
    }
    assert (
        "proposition:0001-example-proposition",
        "synthesis:0001-example-synthesis",
        "sci:synthesizes",
        "synthesizes",
        True,
    ) in rows
    assert (
        sum(
            1
            for row in links["links"]
            if row["source"] == "proposition:0001-example-proposition"
            and row["target"] == "synthesis:0001-example-synthesis"
            and row["predicate"] == "sci:synthesizes"
            and row["link_role"] == "synthesizes"
        )
        == 1
    )
    assert not any(row["predicate"] == "cito:supports" for row in links["links"])
    assert not any(row["predicate"] == "sci:implements" for row in links["links"])
    skipped = [
        warning
        for warning in diagnostics["warnings"]
        if warning["message"].startswith("graph links skipped:")
    ]
    assert len(skipped) == 1


def test_export_labnote_package_data_version_changes_with_graph_links(tmp_path: Path) -> None:
    project_root = tmp_path / "pais"
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_minimal_project(project_root)

    export_labnote_package(project_root=project_root, out_dir=first)
    write_text(
        project_root / "knowledge" / "graph.trig",
        """
        @prefix sci: <http://example.org/science/vocab/> .

        <http://example.org/project/graph/knowledge> {
          <http://example.org/project/proposition/0001-example-proposition>
            sci:synthesizes
            <http://example.org/project/synthesis/0001-example-synthesis> .
        }
        """,
    )
    export_labnote_package(project_root=project_root, out_dir=second)

    assert read_json(first / "manifest.json")["data_version"] != read_json(second / "manifest.json")[
        "data_version"
    ]


def test_science_labnote_export_cli_writes_package(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    project_root = tmp_path / "pais"
    out = tmp_path / "out"
    write_minimal_project(project_root)

    result = CliRunner().invoke(
        main,
        ["labnote", "export", "--project-root", str(project_root), "--out", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert (out / "project.json").exists()
    assert (out / "manifest.json").exists()
    assert "Exported Labnote package" in result.output


def test_science_labnote_export_cli_reports_expected_export_errors(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    project_root = tmp_path / "missing-config"
    project_root.mkdir()
    out = tmp_path / "out"

    result = CliRunner().invoke(
        main,
        ["labnote", "export", "--project-root", str(project_root), "--out", str(out)],
    )

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "missing science.yaml" in result.output
    assert "Traceback" not in result.output

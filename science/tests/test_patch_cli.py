from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, URIRef

from science_tool.cli import main
from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.materialize import materialize_graph


def _write_entity(path: Path, frontmatter: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter, "---", "", "Body.", ""]), encoding="utf-8")


def _project(root: Path) -> None:
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write_entity(
        root / "entities" / "hypotheses" / "h1.md",
        [
            'id: "hypothesis:h1"',
            'type: "hypothesis"',
            'title: "H1"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )
    _write_entity(
        root / "entities" / "propositions" / "p1.md",
        [
            'id: "proposition:p1"',
            'type: "proposition"',
            'title: "P1"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'discusses: ["hypothesis:h1"]',
        ],
    )
    _write_entity(
        root / "entities" / "patches" / "local-demo.md",
        [
            'id: "patch-definition:local-demo"',
            'type: "patch-definition"',
            'title: "Local demo patch"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'focal: "hypothesis:h1"',
            "scope_set:",
            '  - scope: "local"',
            "neighborhood_policy:",
            '  name: "local-closure-v1"',
            '  version: "local-closure-v1"',
            "  max_depth: 2",
            'seeds: ["proposition:p1"]',
        ],
    )


def test_patch_explain_reports_members(tmp_path: Path) -> None:
    _project(tmp_path)
    materialize_graph(tmp_path, strict=False)
    runner = CliRunner()

    result = runner.invoke(main, ["patch", "explain", "patch-definition:local-demo", "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "patch-definition:local-demo" in result.output
    assert "proposition:p1" in result.output
    assert "seed" in result.output


def test_patch_explain_unknown_id_errors(tmp_path: Path) -> None:
    _project(tmp_path)
    materialize_graph(tmp_path, strict=False)
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["patch", "explain", "patch-definition:does-not-exist", "--project-root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "patch definition not found" in result.output


def test_patch_check_passes_for_fresh_graph(tmp_path: Path) -> None:
    _project(tmp_path)
    materialize_graph(tmp_path, strict=False)
    runner = CliRunner()

    result = runner.invoke(main, ["patch", "check", "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "patch check: OK" in result.output


def test_patch_check_detects_orphan_convenience_edge(tmp_path: Path) -> None:
    _project(tmp_path)
    graph_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(graph_path), format="trig")
    patch_uri = URIRef(PROJECT_NS["patch-definition/local-demo"])
    orphan = URIRef(PROJECT_NS["proposition/orphan"])
    ds.graph(patch_uri).add((patch_uri, SCI_NS.hasMember, orphan))
    ds.serialize(destination=str(graph_path), format="trig")
    runner = CliRunner()

    result = runner.invoke(main, ["patch", "check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "without a sci:PatchMembership node" in result.output


def test_patch_check_detects_stale_graph_after_source_edit(tmp_path: Path) -> None:
    _project(tmp_path)
    materialize_graph(tmp_path, strict=False)
    patch_file = tmp_path / "entities" / "patches" / "local-demo.md"
    text = patch_file.read_text(encoding="utf-8")
    patch_file.write_text(
        text.replace(
            'seeds: ["proposition:p1"]',
            'excludes:\n  - ref: "proposition:p1"\n    reason: "out of scope"',
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(main, ["patch", "check", "--project-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "stale patch membership" in result.output

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Namespace
from rdflib import Literal
from rdflib.namespace import RDF, SKOS

from science_tool.cli import main
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import diff_graph_inputs


PROJECT_NS = Namespace("http://example.org/project/")
SCI = Namespace("http://example.org/science/vocab/")
PROV = Namespace("http://www.w3.org/ns/prov#")
SCHEMA = Namespace("https://schema.org/")


def _write_demo_project(
    project_root: Path,
    *,
    include_missing_relation: bool = False,
    include_alias_collision: bool = False,
    include_case_distinct_urls: bool = False,
) -> None:
    project_root.mkdir(parents=True)
    (project_root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  curated: [bio]",
                "  local: project_specific",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project_root / "specs" / "hypotheses").mkdir(parents=True)
    (project_root / "doc" / "questions").mkdir(parents=True)
    (project_root / "tasks").mkdir(parents=True)

    related = '["question:q01-demo", "GO:0008150"]'
    if include_missing_relation:
        related = '["question:q01-demo", "question:q99-missing", "GO:0008150"]'
    if include_case_distinct_urls:
        related = '["question:q01-demo", "https://Example.org/MixedCase", "https://example.org/mixedcase"]'

    (project_root / "specs" / "hypotheses" / "h01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "hypothesis:h01-demo"',
                'type: "hypothesis"',
                'title: "Demo hypothesis"',
                'status: "proposed"',
                "tags: [demo]",
                "ontology_terms: [GO:0008150]",
                "source_refs: []",
                f"related: {related}",
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Demo hypothesis body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (project_root / "doc" / "questions" / "q01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "question:q01-demo"',
                'type: "question"',
                'title: "Demo question"',
                'status: "open"',
                "tags: [demo]",
                "ontology_terms: []",
                'source_refs: ["hypothesis:h01-demo"]',
                'related: ["task:t001"]',
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Demo question body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    if include_alias_collision:
        (project_root / "specs" / "hypotheses" / "h02-demo.md").write_text(
            "\n".join(
                [
                    "---",
                    'id: "hypothesis:h02-demo"',
                    'type: "hypothesis"',
                    'title: "Conflicting alias hypothesis"',
                    "aliases: [H01]",
                    'status: "proposed"',
                    "tags: [demo]",
                    "ontology_terms: []",
                    "source_refs: []",
                    "related: []",
                    'created: "2026-03-12"',
                    'updated: "2026-03-12"',
                    "---",
                    "",
                    "Second hypothesis body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    (project_root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Validate H01",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [hypothesis:h01-demo, question:q01-demo]",
                "- blocked-by: [task:t002]",
                "- created: 2026-03-12",
                "",
                "Do it.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (project_root / "tasks" / "done").mkdir(parents=True)
    (project_root / "tasks" / "done" / "2026-03.md").write_text(
        "\n".join(
            [
                "## [t002] Gather evidence",
                "- type: research",
                "- priority: P2",
                "- status: done",
                "- related: [hypothesis:h01-demo]",
                "- created: 2026-03-11",
                "- completed: 2026-03-12",
                "",
                "Done.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_materialize_graph_includes_task_nodes_and_canonical_links(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    task_uri = PROJECT_NS["task/t001"]
    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (task_uri, RDF.type, SCI.Task) in knowledge
    assert (task_uri, SCHEMA.identifier, None) in knowledge
    assert (task_uri, SKOS.prefLabel, None) in knowledge
    assert (task_uri, SCI.profile, Literal("core")) in knowledge
    assert (hypothesis_uri, SCI.profile, Literal("core")) in knowledge
    assert (task_uri, SCI.tests, hypothesis_uri) in knowledge
    assert (task_uri, SCI.tests, question_uri) in knowledge


def test_materialize_graph_writes_bridge_layer_for_external_terms(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    hypothesis_uri = PROJECT_NS["hypothesis/h01-demo"]
    question_uri = PROJECT_NS["question/q01-demo"]
    external_uri = PROJECT_NS["external/go/0008150"]

    assert (hypothesis_uri, SCI.about, external_uri) in bridge
    assert (external_uri, RDF.type, SCI.ExternalTerm) in bridge
    assert (external_uri, SCHEMA.identifier, None) in bridge
    assert (hypothesis_uri, PROV.wasDerivedFrom, None) in provenance
    assert (question_uri, PROV.wasDerivedFrom, hypothesis_uri) in provenance


def test_materialize_graph_preserves_case_distinct_external_urls(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_case_distinct_urls=True)

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])

    url_nodes = {
        str(subject)
        for subject, _, _ in bridge.triples((None, RDF.type, SCI.ExternalTerm))
        if "/external/url/" in str(subject)
    }
    assert url_nodes == {
        "http://example.org/project/external/url/https%3A%2F%2FExample.org%2FMixedCase",
        "http://example.org/project/external/url/https%3A%2F%2Fexample.org%2Fmixedcase",
    }


def test_graph_audit_reports_unresolved_references(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_missing_relation=True)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "audit", "--project-root", str(project), "--format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert any(
        row["check"] == "unresolved_reference" and row["target"] == "question:q99-missing" for row in payload["rows"]
    )


def test_graph_audit_reports_ambiguous_aliases(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_alias_collision=True)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "audit", "--project-root", str(project), "--format", "json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert any(row["check"] == "ambiguous_alias" and row["target"] == "H01" for row in payload["rows"])


def test_graph_build_materializes_project_graph(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(project)])

    assert result.exit_code == 0
    trig_path = project / "knowledge" / "graph.trig"
    assert trig_path.exists()
    assert diff_graph_inputs(trig_path, "hash") == []


def test_graph_build_fails_cleanly_on_unresolved_references(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project, include_missing_relation=True)

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(project)])

    assert result.exit_code != 0
    assert "unresolved references" in result.output.lower()

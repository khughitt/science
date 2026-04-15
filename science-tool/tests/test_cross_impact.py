from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.cli import main
from science_tool.graph.cross_impact import query_cross_impact
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE, SCI_NS, save_graph_dataset

PROJECT_NS = Namespace("http://example.org/project/")
CITO = Namespace("http://purl.org/spar/cito/")
SCHEMA = Namespace("http://schema.org/")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    return gp


def _invoke(runner: CliRunner, graph_path: Path, args: list[str]) -> None:
    result = runner.invoke(main, [*args, "--path", str(graph_path)])
    assert result.exit_code == 0, result.output


def _set_supports_scope(graph_path: Path, proposition_ref: str, scope: str) -> None:
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    provenance.add((PROJECT_NS[proposition_ref], SCI_NS.supportsScope, Literal(scope)))
    save_graph_dataset(dataset, graph_path)


def _build_local_graph(runner: CliRunner, graph_path: Path) -> None:
    _invoke(runner, graph_path, ["graph", "init"])
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "proposition",
            "Root proposition",
            "--source",
            "article:root",
            "--id",
            "root",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "proposition",
            "Local dependent proposition",
            "--source",
            "article:local",
            "--id",
            "local_dep",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "evidence",
            "proposition/local_dep",
            "proposition/root",
            "--stance",
            "supports",
        ],
    )


def _build_cross_hypothesis_graph(runner: CliRunner, graph_path: Path) -> None:
    _invoke(runner, graph_path, ["graph", "init"])
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "hypothesis",
            "H1",
            "--text",
            "Hypothesis one",
            "--source",
            "paper:h1",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "hypothesis",
            "H2",
            "--text",
            "Hypothesis two",
            "--source",
            "paper:h2",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "proposition",
            "Root proposition",
            "--source",
            "article:root",
            "--id",
            "root",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "proposition",
            "Cross dependent proposition",
            "--source",
            "article:cross",
            "--id",
            "cross_dep",
            "--bridge-between",
            "hypothesis:h1",
            "--bridge-between",
            "hypothesis:h2",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "evidence",
            "proposition/cross_dep",
            "proposition/root",
            "--stance",
            "supports",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "observation",
            "Root signal",
            "--data-source",
            "dataset:obs-1",
            "--id",
            "obs_1",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "finding",
            "Cross dependent finding",
            "--confidence",
            "high",
            "--proposition",
            "proposition/cross_dep",
            "--observation",
            "observation/obs_1",
            "--source",
            "paper:analysis-run-1",
            "--id",
            "finding_cross",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "interpretation",
            "Cross dependent interpretation",
            "--finding",
            "finding/finding_cross",
            "--context",
            "bundle review",
            "--id",
            "interp_cross",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "discussion",
            "Cross dependent discussion",
            "--proposition",
            "proposition/cross_dep",
            "--context",
            "bundle review",
            "--id",
            "disc_cross",
        ],
    )
    _invoke(
        runner,
        graph_path,
        [
            "graph",
            "add",
            "question",
            "cross_q",
            "--text",
            "Does the root proposition generalize?",
            "--source",
            "paper:q1",
            "--related",
            "hypothesis:h1",
            "--related",
            "hypothesis:h2",
        ],
    )
    _set_supports_scope(graph_path, "proposition/root", "project_wide")


def test_cross_impact_local_only_update_returns_local_scope(runner: CliRunner, graph_path: Path) -> None:
    _build_local_graph(runner, graph_path)

    payload = query_cross_impact(graph_path=graph_path, target_ref="proposition/root", limit=10)

    assert payload["scope"] == "local"
    assert payload["target"] == "proposition/root"
    assert payload["rows"] == [
        {
            "dependent_proposition": "proposition/local_dep",
            "dependent_text": "Local dependent proposition",
            "relation": "supports",
            "hypotheses": "-",
            "interpretations": "-",
            "discussions": "-",
            "questions": "-",
            "scope": "local",
            "scope_reason": "direct_link",
        }
    ]


def test_cross_impact_cross_hypothesis_propagates_beyond_bundle(runner: CliRunner, graph_path: Path) -> None:
    _build_cross_hypothesis_graph(runner, graph_path)

    payload = query_cross_impact(graph_path=graph_path, target_ref="proposition/root", limit=10)

    assert payload["scope"] == "project-wide"
    assert payload["target"] == "proposition/root"
    assert payload["rows"] == [
        {
            "dependent_proposition": "proposition/cross_dep",
            "dependent_text": "Cross dependent proposition",
            "relation": "supports",
            "hypotheses": "hypothesis/h1; hypothesis/h2",
            "interpretations": "interpretation/interp_cross",
            "discussions": "discussion/disc_cross",
            "questions": "question/cross_q",
            "scope": "project-wide",
            "scope_reason": "direct_link + hypothesis_bundle + supports_scope(project_wide)",
        }
    ]


def test_cross_impact_missing_node_fails(runner: CliRunner, graph_path: Path) -> None:
    _build_local_graph(runner, graph_path)

    result = runner.invoke(main, ["graph", "cross-impact", "proposition/missing", "--path", str(graph_path)])

    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "missing" in result.output.lower()


def test_cross_impact_json_output_is_deterministic(runner: CliRunner, graph_path: Path) -> None:
    _build_cross_hypothesis_graph(runner, graph_path)

    first = runner.invoke(main, ["graph", "cross-impact", "proposition/root", "--format", "json", "--path", str(graph_path)])
    second = runner.invoke(main, ["graph", "cross-impact", "proposition/root", "--format", "json", "--path", str(graph_path)])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first.output == second.output

    payload = json.loads(first.output)
    assert payload["target"] == "proposition/root"
    assert payload["scope"] == "project-wide"
    assert isinstance(payload["rows"], list)


def test_cross_impact_query_stays_under_five_seconds_on_large_fixture(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)

    dataset = Dataset()
    dataset.parse(data=INITIAL_GRAPH_TEMPLATE, format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    root = PROJECT_NS["proposition/root"]
    knowledge.add((root, RDF.type, SCI_NS.Proposition))
    knowledge.add((root, SCHEMA.text, Literal("Root proposition")))

    for index in range(800):
        prop = PROJECT_NS[f"proposition/dependent_{index:04d}"]
        hyp_a = PROJECT_NS["hypothesis/h1" if index % 2 == 0 else "hypothesis/h2"]
        hyp_b = PROJECT_NS["hypothesis/h2" if index % 2 == 0 else "hypothesis/h1"]
        knowledge.add((prop, RDF.type, SCI_NS.Proposition))
        knowledge.add((prop, SCHEMA.text, Literal(f"Dependent proposition {index}")))
        knowledge.add((prop, CITO.discusses, hyp_a))
        knowledge.add((prop, CITO.discusses, hyp_b))
        knowledge.add((prop, CITO.supports, root))
        provenance.add((prop, PROV.wasDerivedFrom, URIRef(f"http://example.org/source/{index}")))

    provenance.add((root, SCI_NS.supportsScope, Literal("project_wide")))
    save_graph_dataset(dataset, graph_path)

    started = time.perf_counter()
    payload = query_cross_impact(graph_path=graph_path, target_ref="proposition/root", limit=1000)
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert payload["scope"] == "project-wide"
    assert len(payload["rows"]) == 800

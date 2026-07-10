from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS

from science_tool.cli import main
from science_tool.graph.cross_impact import query_cross_impact
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE, SCHEMA_NS, SCI_NS, save_graph_dataset

PROJECT_NS = Namespace("http://example.org/project/")
CITO = Namespace("http://purl.org/spar/cito/")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    return gp


def _set_supports_scope(graph_path: Path, proposition_ref: str, scope: str) -> None:
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    provenance.add((PROJECT_NS[proposition_ref], SCI_NS.supportsScope, Literal(scope)))
    save_graph_dataset(dataset, graph_path)


def _seed_dataset() -> Dataset:
    dataset = Dataset()
    dataset.parse(data=INITIAL_GRAPH_TEMPLATE, format="trig")
    return dataset


def _write_hypothesis(knowledge, slug: str, text: str) -> URIRef:
    uri = PROJECT_NS[f"hypothesis/{slug}"]
    knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((uri, SCHEMA_NS.text, Literal(text)))
    return uri


def _write_proposition(knowledge, slug: str, text: str) -> URIRef:
    uri = PROJECT_NS[f"proposition/{slug}"]
    knowledge.add((uri, RDF.type, SCI_NS.Proposition))
    knowledge.add((uri, SCHEMA_NS.text, Literal(text)))
    return uri


def _build_local_graph(graph_path: Path) -> None:
    dataset = _seed_dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    root = _write_proposition(knowledge, "root", "Root proposition")
    local_dep = _write_proposition(knowledge, "local_dep", "Local dependent proposition")
    knowledge.add((local_dep, CITO.supports, root))

    save_graph_dataset(dataset, graph_path)


def _build_cross_hypothesis_graph(graph_path: Path) -> None:
    dataset = _seed_dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    h1 = _write_hypothesis(knowledge, "h1", "Hypothesis one")
    h2 = _write_hypothesis(knowledge, "h2", "Hypothesis two")
    root = _write_proposition(knowledge, "root", "Root proposition")
    cross_dep = _write_proposition(knowledge, "cross_dep", "Cross dependent proposition")
    knowledge.add((cross_dep, CITO.supports, root))
    knowledge.add((cross_dep, CITO.discusses, h1))
    knowledge.add((cross_dep, CITO.discusses, h2))

    question = PROJECT_NS["question/cross_q"]
    knowledge.add((question, RDF.type, SCI_NS.Question))
    knowledge.add((question, SCHEMA_NS.text, Literal("Does the root proposition generalize?")))
    knowledge.add((question, SKOS.related, h1))
    knowledge.add((question, SKOS.related, h2))

    save_graph_dataset(dataset, graph_path)
    _set_supports_scope(graph_path, "proposition/root", "project_wide")


def _build_mm30_sized_fixture_graph(graph_path: Path) -> None:
    dataset = Dataset()
    dataset.parse(data=INITIAL_GRAPH_TEMPLATE, format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    root = PROJECT_NS["proposition/root"]
    knowledge.add((root, RDF.type, SCI_NS.Proposition))
    knowledge.add((root, SCHEMA_NS.text, Literal("Root proposition")))

    for index in range(800):
        prop = PROJECT_NS[f"proposition/dependent_{index:04d}"]
        hyp_a = PROJECT_NS["hypothesis/h1" if index % 2 == 0 else "hypothesis/h2"]
        hyp_b = PROJECT_NS["hypothesis/h2" if index % 2 == 0 else "hypothesis/h1"]
        knowledge.add((prop, RDF.type, SCI_NS.Proposition))
        knowledge.add((prop, SCHEMA_NS.text, Literal(f"Dependent proposition {index}")))
        knowledge.add((prop, CITO.discusses, hyp_a))
        knowledge.add((prop, CITO.discusses, hyp_b))
        knowledge.add((prop, CITO.supports, root))
        provenance.add((prop, PROV.wasDerivedFrom, URIRef(f"http://example.org/source/{index}")))

    provenance.add((root, SCI_NS.supportsScope, Literal("project_wide")))
    save_graph_dataset(dataset, graph_path)


@pytest.fixture
def mm30_sized_graph_path(tmp_path: Path) -> Path:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    _build_mm30_sized_fixture_graph(graph_path)
    return graph_path


def test_cross_impact_local_only_update_returns_local_scope(runner: CliRunner, graph_path: Path) -> None:
    _build_local_graph(graph_path)

    payload = query_cross_impact(graph_path=graph_path, target_ref="proposition/root", limit=10)

    assert payload["scope"] == "local"
    assert payload["target"] == "proposition/root"
    assert payload["rows"] == [
        {
            "dependent_proposition": "proposition/local_dep",
            "dependent_text": "Local dependent proposition",
            "relation": "supports",
            "hypotheses": "-",
            "questions": "-",
            "scope": "local",
            "scope_reason": "direct_link",
        }
    ]


def test_cross_impact_cross_hypothesis_propagates_beyond_bundle(runner: CliRunner, graph_path: Path) -> None:
    _build_cross_hypothesis_graph(graph_path)

    payload = query_cross_impact(graph_path=graph_path, target_ref="proposition/root", limit=10)

    assert payload["scope"] == "project-wide"
    assert payload["target"] == "proposition/root"
    assert payload["rows"] == [
        {
            "dependent_proposition": "proposition/cross_dep",
            "dependent_text": "Cross dependent proposition",
            "relation": "supports",
            "hypotheses": "hypothesis/h1; hypothesis/h2",
            "questions": "question/cross_q",
            "scope": "project-wide",
            "scope_reason": "direct_link + hypothesis_bundle + supports_scope(project_wide)",
        }
    ]


def test_cross_impact_missing_node_fails(runner: CliRunner, graph_path: Path) -> None:
    _build_local_graph(graph_path)

    result = runner.invoke(main, ["graph", "cross-impact", "proposition/missing", "--path", str(graph_path)])

    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "missing" in result.output.lower()


def test_cross_impact_json_output_is_deterministic(runner: CliRunner, graph_path: Path) -> None:
    _build_cross_hypothesis_graph(graph_path)

    first = runner.invoke(
        main, ["graph", "cross-impact", "proposition/root", "--format", "json", "--path", str(graph_path)]
    )
    second = runner.invoke(
        main, ["graph", "cross-impact", "proposition/root", "--format", "json", "--path", str(graph_path)]
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert first.output == second.output

    payload = json.loads(first.output)
    assert payload["target"] == "proposition/root"
    assert payload["scope"] == "project-wide"
    assert isinstance(payload["rows"], list)


def test_cross_impact_query_stays_under_five_seconds_on_large_fixture(
    mm30_sized_graph_path: Path,
) -> None:
    started = time.perf_counter()
    payload = query_cross_impact(
        graph_path=mm30_sized_graph_path,
        target_ref="proposition/root",
        limit=1000,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert payload["scope"] == "project-wide"
    assert len(payload["rows"]) == 800

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.cli import main
from science_tool.graph.io import PROJECT_NS, SCI_NS, save_canonical_graph_dataset
from science_tool.wander.provenance import PROV_WAS_DERIVED_FROM, SCHEMA_IDENTIFIER


def _build_fixture_graph(tmp_path: Path) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    for slug, label in (("h1", "First"), ("h2", "Second"), ("h3", "Third")):
        uri = URIRef(PROJECT_NS[f"hypothesis/{slug}"])
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
        source_path = tmp_path / "doc" / f"{slug}.md"
        source_path.parent.mkdir(exist_ok=True)
        source_path.write_text(f"# {label}\n")
        source_uri = URIRef(PROJECT_NS[f"source/doc_{slug}.md"])
        provenance.add((uri, PROV_WAS_DERIVED_FROM, source_uri))
        provenance.add((source_uri, SCHEMA_IDENTIFIER, Literal(str(source_path))))
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    save_canonical_graph_dataset(dataset, graph_path)
    return graph_path


def _authored_last_reviewed_graph(tmp_path: Path, lexical: str) -> Path:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(
        f'''@prefix sci: <http://example.org/science/vocab/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/project/graph/knowledge> {{
  <http://example.org/project/hypothesis/h1>
    a sci:Hypothesis ;
    skos:prefLabel "h1" ;
    sci:freshnessState "fresh" ;
    sci:lastReviewed "{lexical}"^^xsd:date .
}}
'''
    )
    return graph_path


def test_wander_writes_markdown_skeleton(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)
    out_path = tmp_path / "walk.md"

    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n",
            "3",
            "--seed",
            "42",
            "--graph-path",
            str(graph_path),
            "--format",
            "markdown",
            "--out",
            str(out_path),
            "--today",
            "2026-05-09",
        ],
    )

    assert result.exit_code == 0, result.output
    text = out_path.read_text()
    assert text.startswith("---\n")
    assert "## Per-entity review" in text
    assert "## Pairwise connections" in text


def test_wander_json_output_is_well_formed(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n",
            "2",
            "--seed",
            "42",
            "--graph-path",
            str(graph_path),
            "--format",
            "json",
            "--today",
            "2026-05-09",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["seed"] == 42
    assert len(payload["bundles"]) == 2


def test_wander_today_option_still_accepted(tmp_path: Path) -> None:
    # --today survives the attention `today` removal because it dates the walk and stub-smell.
    graph_path = _build_fixture_graph(tmp_path)
    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n",
            "1",
            "--seed",
            "1",
            "--graph-path",
            str(graph_path),
            "--format",
            "json",
            "--today",
            "2026-05-01",
        ],
    )
    assert result.exit_code == 0, result.output


def test_wander_seed_is_reproducible(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)

    runs = []
    for _ in range(2):
        result = CliRunner().invoke(
            main,
            [
                "wander",
                "--n",
                "2",
                "--seed",
                "42",
                "--graph-path",
                str(graph_path),
                "--format",
                "json",
                "--today",
                "2026-05-09",
            ],
        )
        runs.append([b["entity_id"] for b in json.loads(result.output)["bundles"]])

    assert runs[0] == runs[1]


def test_wander_kind_filter_restricts_sample(tmp_path: Path) -> None:
    graph_path = _build_fixture_graph(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n",
            "5",
            "--seed",
            "42",
            "--graph-path",
            str(graph_path),
            "--kind",
            "proposition",
            "--format",
            "json",
            "--today",
            "2026-05-09",
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["bundles"] == []


def test_wander_errors_with_actionable_message_when_graph_missing(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        [
            "wander",
            "--n",
            "1",
            "--graph-path",
            str(tmp_path / "missing.trig"),
            "--today",
            "2026-05-09",
        ],
    )

    assert result.exit_code != 0
    assert "science graph build" in result.output


def test_wander_preserves_authored_noncanonical_last_reviewed_error(tmp_path: Path) -> None:
    lexical = "2026-05-01+05:00"
    graph_path = _authored_last_reviewed_graph(tmp_path, lexical)

    result = CliRunner().invoke(
        main,
        ["wander", "--n", "1", "--graph-path", str(graph_path), "--format", "json"],
    )

    assert result.exit_code != 0
    assert "hypothesis:h1" in result.output
    assert lexical in result.output

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.cli import main
from science_tool.graph.attention import compute_attention_candidates, weighted_sample_without_replacement
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS, save_canonical_graph_dataset


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _attention_fixture() -> Dataset:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    h1 = _u("hypothesis/h1")
    h2 = _u("hypothesis/h2")
    h3 = _u("hypothesis/h3")
    source_a = _u("article/source_a")
    source_b = _u("workflow-run/source_b")
    support = _u("observation/support")
    dispute = _u("proposition/dispute")

    for uri, label in (
        (h1, "Contested hypothesis"),
        (h2, "Fresh hypothesis"),
        (h3, "Quiet hypothesis"),
    ):
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))

    knowledge.add((h1, SCI_NS.freshnessState, Literal("needs-review")))
    knowledge.add((h1, SCI_NS.lastReviewed, Literal("2026-04-01", datatype=XSD.date)))
    knowledge.add((source_a, SCI_NS.bearsOn, h1))
    knowledge.add((source_b, SCI_NS.bearsOn, h1))
    knowledge.add((support, CITO_NS.supports, h1))
    knowledge.add((dispute, CITO_NS.disputes, h1))

    knowledge.add((h2, SCI_NS.freshnessState, Literal("fresh")))
    knowledge.add((h2, SCI_NS.lastReviewed, Literal("2026-04-30", datatype=XSD.date)))
    knowledge.add((support, CITO_NS.supports, h2))

    knowledge.add((h3, SCI_NS.freshnessState, Literal("fresh")))

    return dataset


def test_attention_weight_uses_observable_graph_features() -> None:
    candidates = compute_attention_candidates(_attention_fixture(), today=date(2026, 5, 1))
    by_id = {candidate.entity_id: candidate for candidate in candidates}

    contested = by_id["hypothesis:h1"]
    fresh = by_id["hypothesis:h2"]

    assert contested.weight > fresh.weight
    assert contested.components == {
        "incoming_bears_on": 2.0,
        "days_since_last_review": 30.0,
        "freshness_multiplier": 3.0,
        "support_count": 1.0,
        "dispute_count": 1.0,
        "evidence_balance_factor": 2.0,
        "epsilon": 0.05,
    }


def test_weighted_sampling_is_seeded_and_without_replacement() -> None:
    candidates = compute_attention_candidates(_attention_fixture(), today=date(2026, 5, 1))

    first = weighted_sample_without_replacement(candidates, limit=2, seed=17)
    second = weighted_sample_without_replacement(candidates, limit=2, seed=17)

    assert [candidate.entity_id for candidate in first] == [candidate.entity_id for candidate in second]
    assert len({candidate.entity_id for candidate in first}) == 2


def test_epsilon_floor_keeps_quiet_candidates_sampleable() -> None:
    candidates = compute_attention_candidates(_attention_fixture(), today=date(2026, 5, 1))

    sample = weighted_sample_without_replacement(candidates, limit=10, seed=5)

    assert {candidate.entity_id for candidate in sample} == {
        "hypothesis:h1",
        "hypothesis:h2",
        "hypothesis:h3",
    }
    assert all(candidate.weight > 0 for candidate in sample)


def test_graph_attention_sample_cli_outputs_seeded_json(tmp_path: Path) -> None:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    save_canonical_graph_dataset(
        _attention_fixture(),
        graph_path,
        preferred_graph_order=[PROJECT_NS["graph/knowledge"]],
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "graph",
            "attention-sample",
            "--path",
            str(graph_path),
            "--limit",
            "2",
            "--seed",
            "17",
            "--today",
            "2026-05-01",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    rows = json.loads(result.output)["rows"]
    assert len(rows) == 2
    assert rows[0]["id"]
    assert rows[0]["attention_weight"]
    assert rows[0]["freshness_state"]

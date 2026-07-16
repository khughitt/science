"""Preconditions for the ``graph/attention.py`` instruments (silent-instrument ruling).

``compute_attention_candidates`` reads exactly one layer — ``graph/knowledge`` —
and gates candidacy on exactly one predicate: ``sci:freshnessState``. rdflib's
``Dataset.graph()`` CREATES an empty graph when the layer is absent, so a project
whose graph lacks the knowledge layer, and a project whose freshness pass never
ran, both used to yield ``[]`` — indistinguishable from "nothing deserves
attention". Reporting zero candidates there tells the user everything is
attended-to, which is the exact silent-instrument failure.

Pinned here:

- ``unwired`` (``freshness_state_absent``) — no ``sci:freshnessState`` triple
  exists at all, so no entity has been assessed for attention.
- ``empty``   — the instrument RAN over freshness-bearing entities and the
  caller's own filter (e.g. a ``kinds`` typo) selected none of them. A true zero.
- The samplers PROPAGATE the unwired: a sample of an instrument that did not run
  is not a sample.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.cli import main
from science_tool.graph.attention import (
    compute_attention_candidates,
    query_attention_ranked,
    query_attention_sample,
)
from science_tool.graph.io import PROJECT_NS, SCI_NS, save_canonical_graph_dataset
from science_tool.wander.sampling import WanderSamplerError, sample_for_walk

FRESHNESS_STATE_ABSENT = "freshness_state_absent"


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _dataset_without_freshness() -> Dataset:
    """Entities exist and are labelled — but the freshness pass never stamped them."""
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug, label in (("h1", "First"), ("h2", "Second")):
        uri = _u(f"hypothesis/{slug}")
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))
    return dataset


def _dataset_with_freshness() -> Dataset:
    dataset = _dataset_without_freshness()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug in ("h1", "h2"):
        knowledge.add((_u(f"hypothesis/{slug}"), SCI_NS.freshnessState, Literal("fresh")))
    return dataset


def _write(tmp_path: Path, dataset: Dataset) -> Path:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    save_canonical_graph_dataset(dataset, graph_path, preferred_graph_order=[PROJECT_NS["graph/knowledge"]])
    return graph_path


def _reviewed_and_never_graph(tmp_path: Path) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug, reviewed in [("stamped", "2026-04-30"), ("never", None)]:
        uri = _u(f"hypothesis/{slug}")
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(slug)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
        if reviewed is not None:
            knowledge.add((uri, SCI_NS.lastReviewed, Literal(reviewed, datatype=XSD.date)))
    return _write(tmp_path, dataset)


@pytest.mark.parametrize("command", ["attention-sample", "attention-rank"])
def test_attention_tables_render_last_reviewed(tmp_path: Path, command: str) -> None:
    graph_path = _reviewed_and_never_graph(tmp_path)
    args = ["graph", command, "--path", str(graph_path)]
    if command == "attention-sample":
        args += ["--limit", "5", "--seed", "1"]
    result = CliRunner().invoke(main, args, env={"COLUMNS": "220"})
    assert result.exit_code == 0, result.output
    assert "Last reviewed" in result.output
    assert "2026-04-30" in result.output
    assert "never" in result.output
    assert "365" not in result.output


@pytest.mark.parametrize("command", ["attention-sample", "attention-rank"])
def test_attention_json_surfaces_last_reviewed_without_recency_component(
    tmp_path: Path, command: str
) -> None:
    graph_path = _reviewed_and_never_graph(tmp_path)
    args = ["graph", command, "--path", str(graph_path), "--format", "json"]
    if command == "attention-sample":
        args += ["--limit", "5", "--seed", "1"]

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 0, result.output
    by_id = {row["id"]: row for row in json.loads(result.output)["rows"]}
    assert by_id["hypothesis:stamped"]["last_reviewed"] == "2026-04-30"
    assert by_id["hypothesis:never"]["last_reviewed"] is None
    assert "days_since_last_review" not in by_id["hypothesis:stamped"]
    assert "days_since_last_review" not in by_id["hypothesis:never"]


@pytest.mark.parametrize("command", ["attention-sample", "attention-rank"])
def test_corrupt_last_reviewed_is_clean_cli_error(tmp_path: Path, command: str) -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    uri = _u("hypothesis/h1")
    knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((uri, SKOS.prefLabel, Literal("h1")))
    knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
    knowledge.add(
        (uri, SCI_NS.lastReviewed, Literal("2026-05-01garbage", datatype=XSD.date, normalize=False))
    )
    graph_path = _write(tmp_path, dataset)

    args = ["graph", command, "--path", str(graph_path)]
    if command == "attention-sample":
        args += ["--limit", "5"]
    result = CliRunner().invoke(main, args, env={"COLUMNS": "220"})
    assert result.exit_code != 0
    assert "hypothesis:h1" in result.output
    assert "2026-05-01garbage" in result.output


# --------------------------------------------------------------------------
# unwired: the instrument could not run
# --------------------------------------------------------------------------


def test_candidates_unwired_when_no_freshness_state_exists() -> None:
    result = compute_attention_candidates(_dataset_without_freshness())

    assert result.status == "unwired"
    assert result.code == FRESHNESS_STATE_ABSENT
    assert result.rows == []


def test_candidates_unwired_when_knowledge_layer_is_absent() -> None:
    """``Dataset.graph()`` fabricates the missing layer, so the absent-layer case is
    indistinguishable from the never-stamped case — and must fail the same way."""
    result = compute_attention_candidates(Dataset())

    assert result.status == "unwired"
    assert result.code == FRESHNESS_STATE_ABSENT


# --------------------------------------------------------------------------
# The positive control: the guard must not simply refuse everything
# --------------------------------------------------------------------------


def test_candidates_ok_when_freshness_state_is_present() -> None:
    result = compute_attention_candidates(_dataset_with_freshness())

    assert result.status == "ok"
    assert {candidate.entity_id for candidate in result.rows} == {"hypothesis:h1", "hypothesis:h2"}


def test_compute_attention_candidates_rejects_today_kwarg() -> None:
    # `today` was removed with the recency term; passing it is an error, not a silently-ignored control.
    with pytest.raises(TypeError):
        compute_attention_candidates(_dataset_with_freshness(), today=date(2026, 5, 1))


def test_graph_attention_commands_have_no_today_option() -> None:
    for command in ("attention-sample", "attention-rank"):
        result = CliRunner().invoke(main, ["graph", command, "--today", "2026-05-01"])
        assert result.exit_code != 0
        assert "no such option" in result.output.lower()


def test_kinds_filter_matching_nothing_is_empty_not_unwired() -> None:
    """A ``kinds`` filter that selects none of the freshness-bearing entities is a
    TRUE zero: the instrument ran, and the caller asked about a kind it does not have."""
    result = compute_attention_candidates(_dataset_with_freshness(), kinds={"nosuchkind"})

    assert result.status == "empty"
    assert result.code is None
    assert result.rows == []


# --------------------------------------------------------------------------
# Propagation: a sample of an instrument that did not run is not a sample
# --------------------------------------------------------------------------


def test_query_attention_sample_propagates_unwired(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_without_freshness())

    result = query_attention_sample(graph_path, limit=3, seed=7)

    assert result.status == "unwired"
    assert result.code == FRESHNESS_STATE_ABSENT
    assert result.rows == []


def test_query_attention_ranked_propagates_unwired(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_without_freshness())

    result = query_attention_ranked(graph_path)

    assert result.status == "unwired"
    assert result.code == FRESHNESS_STATE_ABSENT
    assert result.rows == []


def test_query_attention_sample_returns_rows_on_a_freshness_bearing_graph(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_with_freshness())

    result = query_attention_sample(graph_path, limit=2, seed=7)

    assert result.status == "ok"
    assert {row["id"] for row in result.rows} == {"hypothesis:h1", "hypothesis:h2"}


def test_query_attention_ranked_returns_rows_on_a_freshness_bearing_graph(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_with_freshness())

    result = query_attention_ranked(graph_path)

    assert result.status == "ok"
    assert {row["id"] for row in result.rows} == {"hypothesis:h1", "hypothesis:h2"}


def test_query_attention_ranked_empty_on_a_kinds_filter_that_matches_nothing(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_with_freshness())

    result = query_attention_ranked(graph_path, kinds={"nosuchkind"})

    assert result.status == "empty"


# --------------------------------------------------------------------------
# The renderers must refuse to present a walk/table that never ran
# --------------------------------------------------------------------------


def test_attention_rank_cli_refuses_to_render_an_unwired_graph(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_without_freshness())

    result = CliRunner().invoke(main, ["graph", "attention-rank", "--path", str(graph_path)])

    assert result.exit_code != 0
    assert FRESHNESS_STATE_ABSENT in result.output


def test_attention_sample_cli_refuses_to_render_an_unwired_graph(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_without_freshness())

    result = CliRunner().invoke(main, ["graph", "attention-sample", "--path", str(graph_path)])

    assert result.exit_code != 0
    assert FRESHNESS_STATE_ABSENT in result.output


def test_wander_cli_refuses_to_present_an_empty_walk_as_a_completed_one(tmp_path: Path) -> None:
    """The whole point for wander: a graph with no freshness state used to produce a
    walk report with zero entities — a completed-looking walk over an unassessed graph."""
    graph_path = _write(tmp_path, _dataset_without_freshness())

    result = CliRunner().invoke(
        main,
        ["wander", "--n", "2", "--graph-path", str(graph_path), "--format", "json", "--today", "2026-05-01"],
    )

    assert result.exit_code != 0
    assert FRESHNESS_STATE_ABSENT in result.output


def test_sample_for_walk_raises_when_attention_is_unwired(tmp_path: Path) -> None:
    graph_path = _write(tmp_path, _dataset_without_freshness())

    with pytest.raises(WanderSamplerError) as excinfo:
        sample_for_walk(graph_path=graph_path, n=2, seed=7)

    assert FRESHNESS_STATE_ABSENT in str(excinfo.value)

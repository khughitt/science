# science/tests/test_autonomous_run_predicates.py
from __future__ import annotations

from pathlib import Path

from rdflib import Graph

from science_tool.graph.autonomous_runs import add_run_record_to_graph, load_run_records
from science_tool.graph.store import SCI_NS
from science_tool.graph.store.constants import PREDICATE_REGISTRY
# Bare module name, not `tests.…`: pytest puts `science/tests/` on sys.path directly.
# `test_graph_origins.py:19` imports across test modules the same way.
from test_autonomous_runs import _write_record


def _sci_predicates(graph: Graph) -> set[str]:
    return {
        f"sci:{str(p).removeprefix(str(SCI_NS))}"
        for _s, p, _o in graph
        if str(p).startswith(str(SCI_NS))
    }


def _emitted_sci_predicates(tmp_path: Path) -> set[str]:
    # The MAXIMAL record: every optional field populated. With the default fixture's
    # absent `triggered_by`, `sci:runTriggeredBy` is never emitted and this test would
    # certify a registry that omits it.
    path = _write_record(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "disposition: clean", "disposition: clean\ntriggered_by: schedule:weekly-curation"
        ),
        encoding="utf-8",
    )
    graph = Graph()
    add_run_record_to_graph(load_run_records(tmp_path)[0], graph)
    emitted = _sci_predicates(graph)
    assert "sci:runTriggeredBy" in emitted, "fixture is no longer maximal"
    return emitted


def test_every_emitted_run_predicate_is_registered(tmp_path: Path) -> None:
    registered = {row["predicate"] for row in PREDICATE_REGISTRY}
    missing = sorted(_emitted_sci_predicates(tmp_path) - registered)
    assert missing == [], f"unregistered run predicates: {missing}"


def test_run_predicates_are_registered_to_the_provenance_layer(tmp_path: Path) -> None:
    emitted = _emitted_sci_predicates(tmp_path)
    layers = {
        row["predicate"]: row["layer"] for row in PREDICATE_REGISTRY if row["predicate"] in emitted
    }
    assert layers, "no run predicates found in the registry"
    assert set(layers.values()) == {"graph/provenance"}

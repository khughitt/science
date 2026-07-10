from __future__ import annotations

from rdflib import Graph, Literal, URIRef

from science_tool.graph.io import SCI_NS
from science_tool.graph.run_resolution import (
    NoRunReason,
    resolve_run_chain,
    resolved_empirical_runs,
)

RUN = URIRef("urn:run:r1")


def _ds(n: int) -> URIRef:
    return URIRef(f"urn:ds:{n}")


def _direct_run_graph() -> Graph:
    g = Graph()
    g.add((_ds(1), SCI_NS.derivationKind, Literal("workflow-run")))
    g.add((_ds(1), SCI_NS.workflowRun, RUN))
    return g


def _inherited_run_graph() -> Graph:
    g = Graph()
    # child --member_of--> parent --workflow-run--> RUN
    g.add((_ds(1), SCI_NS.derivationKind, Literal("member_of")))
    g.add((_ds(1), SCI_NS.memberOfParent, _ds(2)))
    g.add((_ds(2), SCI_NS.derivationKind, Literal("workflow-run")))
    g.add((_ds(2), SCI_NS.workflowRun, RUN))
    return g


def test_direct_run_chain_is_the_dataset_itself() -> None:
    res = resolve_run_chain(_direct_run_graph(), _ds(1), lambda _r: True)
    assert res.run == RUN
    assert res.chain == [_ds(1)]
    assert res.reasons == []


def test_inherited_run_chain_lists_child_then_parent() -> None:
    res = resolve_run_chain(_inherited_run_graph(), _ds(1), lambda _r: True)
    assert res.run == RUN
    assert res.chain == [_ds(1), _ds(2)]
    assert res.reasons == []


def test_unfingerprinted_run_yields_no_run_but_keeps_the_named_run() -> None:
    res = resolve_run_chain(_direct_run_graph(), _ds(1), lambda _r: False)
    assert res.run is None
    assert res.named_run == RUN  # the CLI can still name it
    assert res.reasons == [NoRunReason.RUN_UNFINGERPRINTED]


def test_resolved_empirical_runs_still_matches_chain_resolution() -> None:
    # Behaviour-preserving delegation: the tuple API returns exactly the run
    # (as a one-element list) and reasons the chain resolver computes.
    g = _inherited_run_graph()
    runs, reasons = resolved_empirical_runs(g, _ds(1), lambda _r: True)
    assert runs == [RUN]
    assert reasons == []
    runs2, reasons2 = resolved_empirical_runs(g, _ds(1), lambda _r: False)
    assert runs2 == []
    assert reasons2 == [NoRunReason.RUN_UNFINGERPRINTED]

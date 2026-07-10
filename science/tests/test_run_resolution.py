import pytest
from rdflib import Graph, Literal, URIRef

from science_tool.graph.io import SCI_NS
from science_tool.graph.run_resolution import (
    MemberOfCycleError, NoRunReason, own_derivation_run, resolve_run_chain, resolved_empirical_runs,
)

DS = lambda n: URIRef(f"http://example.org/dataset/{n}")   # noqa: E731
RUN = lambda n: URIRef(f"http://example.org/workflow-run/{n}")  # noqa: E731

ALL_FINGERPRINTED = lambda _run: True    # noqa: E731
NONE_FINGERPRINTED = lambda _run: False  # noqa: E731


def _run_derived(g: Graph, ds: URIRef, run: URIRef) -> None:
    g.add((ds, SCI_NS.derivationKind, Literal("workflow-run")))
    g.add((ds, SCI_NS.workflowRun, run))


def _recipe_derived(g: Graph, ds: URIRef) -> None:
    g.add((ds, SCI_NS.derivationKind, Literal("workflow-recipe")))


def _member_of(g: Graph, ds: URIRef, parent: URIRef) -> None:
    g.add((ds, SCI_NS.derivationKind, Literal("member_of")))
    g.add((ds, SCI_NS.memberOfParent, parent))


def test_own_derivation_run_returns_the_run():
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    assert own_derivation_run(g, DS("a")) == RUN("r1")


def test_own_derivation_run_is_none_for_member_of():
    g = Graph()
    _member_of(g, DS("m"), DS("a"))
    assert own_derivation_run(g, DS("m")) is None


def test_resolved_runs_recurse_through_member_of_to_parent():
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    _member_of(g, DS("m"), DS("a"))
    runs, reasons = resolved_empirical_runs(g, DS("m"), ALL_FINGERPRINTED)
    assert runs == [RUN("r1")] and reasons == []


def test_run_without_a_fingerprint_contributes_nothing():
    """A run is not a fingerprinted run. Failing open here would void the contract."""
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    runs, reasons = resolved_empirical_runs(g, DS("a"), NONE_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.RUN_UNFINGERPRINTED]


def test_member_of_parent_run_must_also_be_fingerprinted():
    g = Graph()
    _run_derived(g, DS("a"), RUN("r1"))
    _member_of(g, DS("m"), DS("a"))
    runs, reasons = resolved_empirical_runs(g, DS("m"), NONE_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.RUN_UNFINGERPRINTED]


def test_member_of_cycle_raises():
    g = Graph()
    _member_of(g, DS("a"), DS("b"))
    _member_of(g, DS("b"), DS("a"))
    with pytest.raises(MemberOfCycleError, match="dataset/a"):
        resolved_empirical_runs(g, DS("a"), ALL_FINGERPRINTED)


def test_member_of_self_loop_raises():
    g = Graph()
    _member_of(g, DS("s"), DS("s"))
    with pytest.raises(MemberOfCycleError, match="dataset/s"):
        resolved_empirical_runs(g, DS("s"), ALL_FINGERPRINTED)


def test_recipe_only_contributes_nothing_with_reason():
    g = Graph()
    _recipe_derived(g, DS("c"))
    runs, reasons = resolved_empirical_runs(g, DS("c"), ALL_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.RECIPE_ONLY]


def test_produced_by_only_is_code_only_no_run():
    g = Graph()
    g.add((DS("d"), SCI_NS.producedBy, URIRef("http://example.org/code-file/x")))
    runs, reasons = resolved_empirical_runs(g, DS("d"), ALL_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.CODE_ONLY_NO_RUN]


def test_raw_external_dataset_is_no_provenance():
    runs, reasons = resolved_empirical_runs(Graph(), DS("e"), ALL_FINGERPRINTED)
    assert runs == [] and reasons == [NoRunReason.NO_PROVENANCE]


def test_unknown_derivation_kind_fails_loud():
    g = Graph()
    g.add((DS("x"), SCI_NS.derivationKind, Literal("teleportation")))
    with pytest.raises(ValueError, match="teleportation"):
        resolved_empirical_runs(g, DS("x"), ALL_FINGERPRINTED)


def test_resolve_run_chain_direct_run_is_the_dataset_itself():
    g = Graph()
    _run_derived(g, DS(1), RUN(1))
    res = resolve_run_chain(g, DS(1), ALL_FINGERPRINTED)
    assert res.run == RUN(1)
    assert res.named_run == RUN(1)
    assert res.chain == [DS(1)]
    assert res.reasons == []


def test_resolve_run_chain_lists_child_then_parent_when_inherited():
    g = Graph()
    _member_of(g, DS(1), DS(2))
    _run_derived(g, DS(2), RUN(1))
    res = resolve_run_chain(g, DS(1), ALL_FINGERPRINTED)
    assert res.run == RUN(1)
    assert res.chain == [DS(1), DS(2)]
    assert res.reasons == []


def test_resolve_run_chain_keeps_named_run_when_unfingerprinted():
    g = Graph()
    _run_derived(g, DS(1), RUN(1))
    res = resolve_run_chain(g, DS(1), NONE_FINGERPRINTED)
    assert res.run is None
    assert res.named_run == RUN(1)  # the CLI can still name it
    assert res.reasons == [NoRunReason.RUN_UNFINGERPRINTED]


def test_resolved_empirical_runs_still_matches_chain_resolution():
    g = Graph()
    _member_of(g, DS(1), DS(2))
    _run_derived(g, DS(2), RUN(1))
    runs, reasons = resolved_empirical_runs(g, DS(1), ALL_FINGERPRINTED)
    assert runs == [RUN(1)]
    assert reasons == []
    runs2, reasons2 = resolved_empirical_runs(g, DS(1), NONE_FINGERPRINTED)
    assert runs2 == []
    assert reasons2 == [NoRunReason.RUN_UNFINGERPRINTED]

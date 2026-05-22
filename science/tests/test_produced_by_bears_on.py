"""Tests for produced_by -> bears_on derivation (Plan C code provenance)."""

from __future__ import annotations

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.freshness import derive_bears_on_from_produced_by_code
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _bears_on_pairs(ds: Dataset) -> set[tuple[str, str]]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}


def _ds_with_produced_by() -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("dataset/d1"), SCI_NS.producedBy, _u("code-file/run.py")))
    return ds


def test_eligible_code_file_bears_on_dataset() -> None:
    ds = _ds_with_produced_by()
    derive_bears_on_from_produced_by_code(ds, eligible_code_files={_u("code-file/run.py")})
    assert (str(_u("code-file/run.py")), str(_u("dataset/d1"))) in _bears_on_pairs(ds)


def test_ineligible_code_file_emits_nothing() -> None:
    ds = _ds_with_produced_by()
    derive_bears_on_from_produced_by_code(ds, eligible_code_files=set())
    assert _bears_on_pairs(ds) == set()


def _bears_on_depth(ds: Dataset, source: URIRef, target: URIRef) -> int | None:
    """Return the minimum sci:bearsOnDepth for (source, target), or None if no edge."""
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    depths: list[int] = []
    for bn, _, _ in knowledge.triples((None, RDF.type, SCI_NS.BearsOnEdge)):
        if (bn, SCI_NS.bearsOnSource, source) in knowledge and (bn, SCI_NS.bearsOnTarget, target) in knowledge:
            for _, _, d in knowledge.triples((bn, SCI_NS.bearsOnDepth, None)):
                depths.append(int(str(d)))
    return min(depths) if depths else None


def test_eligible_code_file_emits_reified_bears_on_edge() -> None:
    """derive_bears_on_from_produced_by_code emits a reified BearsOnEdge at depth 1."""
    ds = _ds_with_produced_by()
    code_uri = _u("code-file/run.py")
    dataset_uri = _u("dataset/d1")
    derive_bears_on_from_produced_by_code(ds, eligible_code_files={code_uri})
    assert _bears_on_depth(ds, code_uri, dataset_uri) == 1

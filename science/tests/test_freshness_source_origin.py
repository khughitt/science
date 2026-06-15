"""derive_freshness: content-derived staleness via SourceSnapshot origins (Slice B)."""

from __future__ import annotations

from datetime import date

from rdflib import Dataset, URIRef

from science_model.entities import EntityClass
from science_tool.graph.freshness import EntityFreshnessInfo, derive_freshness
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _ds(pairs: list[tuple[URIRef, URIRef]]) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, o in pairs:
        knowledge.add((s, SCI_NS.bearsOn, o))
    return ds


def _entity_info() -> dict[str, EntityFreshnessInfo]:
    return {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 5, 1),
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        }
    }


def _state(ds: Dataset, target: URIRef) -> str | None:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for _, _, o in knowledge.triples((target, SCI_NS.freshnessState, None)):
        return str(o)
    return None


def _triggered(ds: Dataset, target: URIRef) -> set[str]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {str(o) for _, _, o in knowledge.triples((target, SCI_NS.triggeredBy, None))}


def test_snapshot_change_after_baseline_marks_needs_review():
    ss = _u("source-snapshot/abc")
    ds = _ds([(ss, _u("hypothesis/h1"))])
    derive_freshness(
        ds,
        entities=_entity_info(),
        today=date(2026, 6, 15),
        source_changes={str(ss): date(2026, 6, 10)},  # after last_reviewed 2026-05-01
    )
    assert _state(ds, _u("hypothesis/h1")) == "needs-review"
    assert _triggered(ds, _u("hypothesis/h1")) == {str(ss)}  # triggeredBy -> snapshot node


def test_snapshot_change_before_baseline_does_not_trigger():
    ss = _u("source-snapshot/abc")
    ds = _ds([(ss, _u("hypothesis/h1"))])
    derive_freshness(
        ds,
        entities=_entity_info(),
        today=date(2026, 6, 15),
        source_changes={str(ss): date(2026, 4, 15)},  # before last_reviewed 2026-05-01
    )
    assert _state(ds, _u("hypothesis/h1")) == "fresh"
    assert _triggered(ds, _u("hypothesis/h1")) == set()


def test_empty_source_changes_preserves_date_driven_behavior():
    ds = _ds([(_u("dataset/d1"), _u("hypothesis/h1"))])
    info = _entity_info()
    info[str(_u("dataset/d1"))] = {
        "kind_class": EntityClass.OPERATIONAL,
        "last_reviewed": None,
        "created": date(2026, 4, 1),
        "updated": date(2026, 4, 1),
        "review_horizon_days": None,
    }
    derive_freshness(ds, entities=info, today=date(2026, 6, 15), source_changes={})
    assert _state(ds, _u("hypothesis/h1")) == "fresh"

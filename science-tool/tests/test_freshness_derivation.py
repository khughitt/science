"""Tests for EpistemicFreshness derivation against last_reviewed timestamps."""

from __future__ import annotations

from datetime import date

from rdflib import Dataset, URIRef

from science_model.entities import EntityClass
from science_tool.graph.freshness import derive_freshness
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _ds_with_bears_on(pairs: list[tuple[URIRef, URIRef]]) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, o in pairs:
        knowledge.add((s, SCI_NS.bearsOn, o))
    return ds


def _state_for(ds: Dataset, target: URIRef) -> str | None:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for _, _, o in knowledge.triples((target, SCI_NS.freshnessState, None)):
        return str(o)
    return None


def _triggered_by(ds: Dataset, target: URIRef) -> set[str]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {str(o) for _, _, o in knowledge.triples((target, SCI_NS.triggeredBy, None))}


def test_freshness_fresh_when_no_upstream_change():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 5, 1),
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("hypothesis/h1")) == "fresh"
    assert _triggered_by(ds, _u("hypothesis/h1")) == set()


def test_freshness_needs_review_when_upstream_changed_after_last_review():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 4, 1),
            "created": date(2026, 3, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 3, 1),
            "updated": date(2026, 5, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("hypothesis/h1")) == "needs-review"
    assert _triggered_by(ds, _u("hypothesis/h1")) == {str(_u("dataset/d1"))}


def test_freshness_falls_back_to_created_when_last_reviewed_unset():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": None,
            "created": date(2026, 5, 2),
            "updated": date(2026, 5, 2),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    # created (2026-05-02) > upstream updated (2026-04-01) => fresh
    assert _state_for(ds, _u("hypothesis/h1")) == "fresh"


def test_freshness_stale_when_horizon_exceeded_without_upstream_change():
    ds = _ds_with_bears_on([])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2025, 1, 1),
            "created": date(2024, 12, 1),
            "updated": date(2025, 1, 1),
            "review_horizon_days": 90,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("hypothesis/h1")) == "stale"


def test_freshness_skips_non_epistemic_entities():
    ds = _ds_with_bears_on([])
    entities = {
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("dataset/d1")) is None  # No freshness emitted.


def test_freshness_emits_upstream_change_at():
    ds = _ds_with_bears_on([
        (_u("dataset/d1"), _u("hypothesis/h1")),
        (_u("dataset/d2"), _u("hypothesis/h1")),
    ])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 4, 1),
            "created": date(2026, 3, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 3, 1),
            "updated": date(2026, 4, 15),
            "review_horizon_days": None,
        },
        str(_u("dataset/d2")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 3, 1),
            "updated": date(2026, 5, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    upstream_at_values = [
        str(o)
        for _, _, o in knowledge.triples((_u("hypothesis/h1"), SCI_NS.upstreamChangeAt, None))
    ]
    assert upstream_at_values == ["2026-05-01"]
    triggered = _triggered_by(ds, _u("hypothesis/h1"))
    assert triggered == {str(_u("dataset/d1")), str(_u("dataset/d2"))}

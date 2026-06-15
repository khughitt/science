"""Tests for EpistemicFreshness derivation against last_reviewed timestamps."""

from __future__ import annotations

from datetime import date

from rdflib import Dataset, URIRef

from science_model.entities import EntityClass
from science_tool.graph.freshness import EntityFreshnessInfo, derive_freshness
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _ds_with_bears_on(pairs: list[tuple[URIRef, URIRef]]) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, o in pairs:
        knowledge.add((s, SCI_NS.bearsOn, o))
    return ds


def _ds_with_relation(source: URIRef, predicate: URIRef, target: URIRef) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((source, predicate, target))
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
    entities: dict[str, EntityFreshnessInfo] = {
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
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    assert _state_for(ds, _u("hypothesis/h1")) == "fresh"
    assert _triggered_by(ds, _u("hypothesis/h1")) == set()


def test_freshness_needs_review_when_upstream_changed_after_last_review():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities: dict[str, EntityFreshnessInfo] = {
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
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    assert _state_for(ds, _u("hypothesis/h1")) == "needs-review"
    assert _triggered_by(ds, _u("hypothesis/h1")) == {str(_u("dataset/d1"))}


def test_freshness_ignores_amends_and_supersedes_edges() -> None:
    h = _u("hypothesis/h1")
    old = _u("interpretation/old")
    new = _u("interpretation/new")
    for predicate in (SCI_NS.amends, SCI_NS.supersedes):
        ds = _ds_with_relation(new, predicate, old)
        entities: dict[str, EntityFreshnessInfo] = {
            str(h): {
                "kind_class": EntityClass.EPISTEMIC,
                "last_reviewed": date(2026, 4, 1),
                "created": date(2026, 3, 1),
                "updated": date(2026, 4, 1),
                "review_horizon_days": None,
            },
            str(old): {
                "kind_class": EntityClass.EPISTEMIC,
                "last_reviewed": date(2026, 4, 1),
                "created": date(2026, 3, 1),
                "updated": date(2026, 4, 1),
                "review_horizon_days": None,
            },
            str(new): {
                "kind_class": EntityClass.EPISTEMIC,
                "last_reviewed": None,
                "created": date(2026, 5, 1),
                "updated": date(2026, 5, 1),
                "review_horizon_days": None,
            },
        }

        derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})

        assert _state_for(ds, h) == "fresh"
        assert _triggered_by(ds, h) == set()


def test_freshness_falls_back_to_created_when_last_reviewed_unset():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities: dict[str, EntityFreshnessInfo] = {
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
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    # created (2026-05-02) > upstream updated (2026-04-01) => fresh
    assert _state_for(ds, _u("hypothesis/h1")) == "fresh"


def test_freshness_stale_when_horizon_exceeded_without_upstream_change():
    ds = _ds_with_bears_on([])
    entities: dict[str, EntityFreshnessInfo] = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2025, 1, 1),
            "created": date(2024, 12, 1),
            "updated": date(2025, 1, 1),
            "review_horizon_days": 90,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    assert _state_for(ds, _u("hypothesis/h1")) == "stale"


def test_freshness_skips_non_epistemic_entities():
    ds = _ds_with_bears_on([])
    entities: dict[str, EntityFreshnessInfo] = {
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    assert _state_for(ds, _u("dataset/d1")) is None  # No freshness emitted.


def test_freshness_emits_upstream_change_at():
    ds = _ds_with_bears_on(
        [
            (_u("dataset/d1"), _u("hypothesis/h1")),
            (_u("dataset/d2"), _u("hypothesis/h1")),
        ]
    )
    entities: dict[str, EntityFreshnessInfo] = {
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
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    upstream_at_values = [str(o) for _, _, o in knowledge.triples((_u("hypothesis/h1"), SCI_NS.upstreamChangeAt, None))]
    assert upstream_at_values == ["2026-05-01"]
    triggered = _triggered_by(ds, _u("hypothesis/h1"))
    assert triggered == {str(_u("dataset/d1")), str(_u("dataset/d2"))}


def test_freshness_needs_review_wins_over_stale_when_both_apply():
    """When both upstream change and horizon-exceeded apply, needs-review wins."""
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities: dict[str, EntityFreshnessInfo] = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2025, 1, 1),  # Long ago
            "created": date(2024, 12, 1),
            "updated": date(2025, 1, 1),
            "review_horizon_days": 90,  # Way exceeded
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2025, 1, 1),
            "updated": date(2026, 5, 1),  # Post-dates baseline
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    # Both conditions apply: upstream change AND horizon exceeded.
    # needs-review must win.
    assert _state_for(ds, _u("hypothesis/h1")) == "needs-review"


def test_derive_freshness_emits_last_reviewed_triple() -> None:
    from rdflib import Literal
    from rdflib.namespace import XSD

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    entities: dict[str, EntityFreshnessInfo] = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 1, 15),
            "created": date(2025, 1, 1),
            "updated": None,
            "review_horizon_days": None,
        }
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 4), source_changes={})

    triples = list(knowledge.triples((h, SCI_NS.lastReviewed, None)))
    assert triples == [(h, SCI_NS.lastReviewed, Literal("2026-01-15", datatype=XSD.date))]


def test_derive_freshness_no_last_reviewed_triple_when_unset() -> None:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    entities: dict[str, EntityFreshnessInfo] = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": None,
            "created": date(2025, 1, 1),
            "updated": None,
            "review_horizon_days": None,
        }
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 4), source_changes={})
    assert list(knowledge.triples((h, SCI_NS.lastReviewed, None))) == []


def test_horizon_boundary_inclusive_at_threshold() -> None:
    """today - baseline == horizon → still fresh (uses strict `>`)."""
    from datetime import date, timedelta
    from rdflib import Dataset, Literal, URIRef
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    baseline = date(2026, 1, 1)
    horizon = 30
    entities: dict[str, EntityFreshnessInfo] = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": baseline,
            "created": baseline,
            "updated": None,
            "review_horizon_days": horizon,
        }
    }
    today_eq = baseline + timedelta(days=horizon)
    derive_freshness(ds, entities=entities, today=today_eq, source_changes={})
    assert (h, SCI_NS.freshnessState, Literal("fresh")) in knowledge


def test_horizon_one_day_past_threshold_is_stale() -> None:
    """today - baseline == horizon + 1 → stale (crosses the strict `>` boundary)."""
    from datetime import date, timedelta
    from rdflib import Dataset, Literal, URIRef
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    baseline = date(2026, 1, 1)
    horizon = 30
    entities: dict[str, EntityFreshnessInfo] = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": baseline,
            "created": baseline,
            "updated": None,
            "review_horizon_days": horizon,
        }
    }
    today_past = baseline + timedelta(days=horizon + 1)
    derive_freshness(ds, entities=entities, today=today_past, source_changes={})
    assert (h, SCI_NS.freshnessState, Literal("stale")) in knowledge


def test_horizon_one_day_minimum() -> None:
    """horizon=1: 1 day after baseline → fresh; 2 days after → stale."""
    from datetime import date, timedelta
    from rdflib import Dataset, Literal, URIRef
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS

    baseline = date(2026, 1, 1)
    entities: dict[str, EntityFreshnessInfo] = {
        "http://example.org/hypothesis/h": {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": baseline,
            "created": baseline,
            "updated": None,
            "review_horizon_days": 1,
        }
    }
    h = URIRef("http://example.org/hypothesis/h")

    # day after baseline → still fresh (today - baseline == 1, not > 1)
    ds1 = Dataset()
    derive_freshness(ds1, entities=entities, today=baseline + timedelta(days=1), source_changes={})
    assert (h, SCI_NS.freshnessState, Literal("fresh")) in ds1.graph(PROJECT_NS["graph/knowledge"])

    # two days after → stale
    ds2 = Dataset()
    derive_freshness(ds2, entities=entities, today=baseline + timedelta(days=2), source_changes={})
    assert (h, SCI_NS.freshnessState, Literal("stale")) in ds2.graph(PROJECT_NS["graph/knowledge"])

"""Tests for check_projection_drift — pure dict-diff for regeneration drift detection."""

from __future__ import annotations

import copy

from science_tool.graph.entity_projection import check_projection_drift


def test_driftcheck_clean_when_matching() -> None:
    """Identical expected and committed dicts return an empty diff."""
    expected = {
        "dataset:mmrf": {"origin": "external", "source_class": "observational"},
        "dataset:gse12345": {"origin": "external", "source_class": "observational"},
    }
    committed = {
        "dataset:mmrf": {"origin": "external", "source_class": "observational"},
        "dataset:gse12345": {"origin": "external", "source_class": "observational"},
    }
    assert check_projection_drift(expected, committed) == {}


def test_driftcheck_detects_field_divergence() -> None:
    """Same id present in both, but one field differs — diff names the id and field."""
    expected = {"dataset:mmrf": {"origin": "external", "source_class": "observational"}}
    committed = {"dataset:mmrf": {"origin": "external", "source_class": "derived"}}

    diff = check_projection_drift(expected, committed)

    assert "dataset:mmrf" in diff
    id_diff = diff["dataset:mmrf"]
    assert "fields" in id_diff
    assert "source_class" in id_diff["fields"]
    field_diff = id_diff["fields"]["source_class"]
    assert field_diff["expected"] == "observational"
    assert field_diff["committed"] == "derived"
    # No spurious status key when there is a field divergence
    assert "status" not in id_diff


def test_driftcheck_detects_missing_id() -> None:
    """Id in expected but absent from committed is flagged as missing."""
    expected = {"dataset:only_expected": {"origin": "external"}}
    committed = {}

    diff = check_projection_drift(expected, committed)

    assert "dataset:only_expected" in diff
    assert diff["dataset:only_expected"]["status"] == "missing_from_committed"


def test_driftcheck_detects_extra_id() -> None:
    """Id in committed but absent from expected is flagged as unexpected."""
    expected = {}
    committed = {"dataset:only_committed": {"origin": "external"}}

    diff = check_projection_drift(expected, committed)

    assert "dataset:only_committed" in diff
    assert diff["dataset:only_committed"]["status"] == "unexpected_in_committed"


def test_driftcheck_is_side_effect_free() -> None:
    """Calling check_projection_drift must not mutate either input dict."""
    expected = {"dataset:mmrf": {"origin": "external", "source_class": "observational"}}
    committed = {"dataset:mmrf": {"origin": "external", "source_class": "derived"}}

    expected_before = copy.deepcopy(expected)
    committed_before = copy.deepcopy(committed)

    check_projection_drift(expected, committed)

    assert expected == expected_before
    assert committed == committed_before


def test_driftcheck_combined_divergences() -> None:
    """All three divergence kinds may appear in a single diff."""
    expected = {
        "dataset:match": {"origin": "external"},
        "dataset:field_drift": {"origin": "external", "source_class": "observational"},
        "dataset:only_expected": {"origin": "external"},
    }
    committed = {
        "dataset:match": {"origin": "external"},
        "dataset:field_drift": {"origin": "external", "source_class": "derived"},
        "dataset:only_committed": {"origin": "external"},
    }

    diff = check_projection_drift(expected, committed)

    # Matching id must NOT appear in the diff
    assert "dataset:match" not in diff

    # Field divergence
    assert "dataset:field_drift" in diff
    assert diff["dataset:field_drift"]["fields"]["source_class"]["expected"] == "observational"
    assert diff["dataset:field_drift"]["fields"]["source_class"]["committed"] == "derived"

    # Missing
    assert "dataset:only_expected" in diff
    assert diff["dataset:only_expected"]["status"] == "missing_from_committed"

    # Extra
    assert "dataset:only_committed" in diff
    assert diff["dataset:only_committed"]["status"] == "unexpected_in_committed"


def test_driftcheck_output_is_deterministic() -> None:
    """Two calls with the same inputs produce equal (and sorted-key-stable) results."""
    expected = {
        "dataset:b": {"origin": "external", "source_class": "observational"},
        "dataset:a": {"origin": "external"},
    }
    committed = {
        "dataset:b": {"origin": "external", "source_class": "derived"},
        "dataset:extra": {"origin": "external"},
    }

    diff1 = check_projection_drift(expected, committed)
    diff2 = check_projection_drift(expected, committed)
    assert diff1 == diff2
    # Keys should be lexicographically sorted for stable serialisation
    assert list(diff1.keys()) == sorted(diff1.keys())

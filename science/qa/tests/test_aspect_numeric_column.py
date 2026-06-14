import pandas as pd
import pytest
from science_qa.aspects.numeric_column import (
    bounds, low_variance, missing_sentinels, polarity, ranges, zero_fraction,
)
from science_qa.context import TableContext
from science_qa.flags import SEVERITY_STRUCTURAL


def _ctx(df, cols):
    return TableContext(table=df, columns=cols)


def test_zero_fraction_flags_all_zero_column_distribution():
    df = pd.DataFrame({"a": [0, 0, 0], "b": [1, 2, 3]})
    flags = zero_fraction(_ctx(df, ["a", "b"]), {})
    assert [f.subject for f in flags] == ["a"]
    assert flags[0].severity == "distribution" and flags[0].source == "numeric-column"


def test_low_variance_flags_constant_column():
    df = pd.DataFrame({"a": [5, 5, 5], "b": [1, 2, 3]})
    flags = low_variance(_ctx(df, ["a", "b"]), {})
    assert [f.subject for f in flags] == ["a"]
    assert flags[0].check == "low_variance"


def test_polarity_flags_negative_values_structural():
    df = pd.DataFrame({"total_counts": [-1, 2]})
    flags = polarity(_ctx(df, ["total_counts"]), {})
    assert flags[0].check == "polarity" and flags[0].severity == "structural"


def test_ranges_flags_min_and_max_distribution():
    df = pd.DataFrame({"g": [0, 50, 9000]})
    flags = ranges(_ctx(df, ["g"]), {"bounds": {"min": 1, "max": 8000}})
    sides = sorted(f.side for f in flags)
    assert sides == ["max", "min"] and all(f.severity == "distribution" for f in flags)


def test_missing_sentinels_flags_survivors_structural():
    df = pd.DataFrame({"x": [-9, 1, 2], "y": [1.0, 2.0, 3.0]})
    flags = missing_sentinels(_ctx(df, ["x", "y"]), {"sentinels": [-9]})
    assert [f.subject for f in flags] == ["x"] and flags[0].severity == "structural"


def _bctx(df, col):
    return TableContext(table=df, columns=[col])


def test_bounds_minimum_violation_is_structural():
    df = pd.DataFrame({"x": [-1, 0, 5]})
    flags = bounds(_bctx(df, "x"), {"bounds": {"minimum": 0}})
    assert len(flags) == 1
    assert flags[0].severity == SEVERITY_STRUCTURAL
    assert flags[0].side == "minimum" and flags[0].value == "1"


def test_bounds_exclusive_maximum_counts_boundary():
    df = pd.DataFrame({"x": [1, 2, 3]})
    flags = bounds(_bctx(df, "x"), {"bounds": {"exclusiveMaximum": 3}})
    assert len(flags) == 1 and flags[0].side == "exclusiveMaximum" and flags[0].value == "1"  # the 3 violates


def test_bounds_min_and_max_use_distinct_bound_key_sides():
    df = pd.DataFrame({"x": [-1, 5, 100]})
    flags = bounds(_bctx(df, "x"), {"bounds": {"minimum": 0, "maximum": 10}})
    assert {f.side for f in flags} == {"minimum", "maximum"}


def test_bounds_inclusive_and_exclusive_min_get_distinct_flag_ids():
    df = pd.DataFrame({"x": [0, 1, 2]})
    flags = bounds(_bctx(df, "x"), {"bounds": {"exclusiveMinimum": 0}})
    assert flags[0].side == "exclusiveMinimum"  # not collapsed to "min"; distinct from "minimum"


def test_bounds_clean_column_no_flags():
    df = pd.DataFrame({"x": [0, 5, 10]})
    assert bounds(_bctx(df, "x"), {"bounds": {"minimum": 0, "maximum": 10}}) == []


def test_bounds_temporal_iso_string():
    df = pd.DataFrame({"d": ["2019-01-01", "2020-06-01", "2021-01-01"]})
    flags = bounds(_bctx(df, "d"), {"bounds": {"minimum": "2020-01-01"}})
    assert len(flags) == 1 and flags[0].value == "1"  # the 2019 date


def test_bounds_uncoercible_column_raises():
    df = pd.DataFrame({"s": ["a", "b", "c"]})
    with pytest.raises(ValueError, match="cannot be coerced"):
        bounds(_bctx(df, "s"), {"bounds": {"minimum": 0}})

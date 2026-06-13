import pandas as pd
from science_qa.aspects.numeric_column import (
    low_variance, missing_sentinels, polarity, ranges, zero_fraction,
)
from science_qa.context import TableContext


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

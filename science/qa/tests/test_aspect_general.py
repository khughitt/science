import pandas as pd

from science_qa.aspects.general import missing_fraction, non_empty
from science_qa.context import TableContext


def _ctx(df):
    return TableContext(table=df, columns=list(df.columns))


def test_non_empty_flags_structural_on_zero_rows():
    flags = non_empty(_ctx(pd.DataFrame({"a": []})), {})
    assert len(flags) == 1
    assert flags[0].severity == "structural"
    assert flags[0].source == "general"
    assert flags[0].check == "non_empty"


def test_non_empty_clears_on_rows_present():
    assert non_empty(_ctx(pd.DataFrame({"a": [1]})), {}) == []


def test_missing_fraction_flags_distribution_only_when_threshold_exceeded():
    df = pd.DataFrame({"a": [1, None, None, None]})  # 75% missing
    assert missing_fraction(_ctx(df), {}) == []                        # no threshold -> no flag
    assert missing_fraction(_ctx(df), {"max_missing_fraction": 0.5})   # exceeded -> flag
    flags = missing_fraction(_ctx(df), {"max_missing_fraction": 0.5})
    assert flags[0].severity == "distribution"

import pandas as pd
from science_qa.aspects.tabular import (
    categoricals, exclusive_flags, required_complete, type_conformance, unique_key,
)
from science_qa.context import TableContext


def _ctx(df, cols):
    return TableContext(table=df, columns=cols)


def test_unique_key_flags_duplicate_keys_structural():
    df = pd.DataFrame({"id": [1, 1, 2]})
    flags = unique_key(_ctx(df, ["id"]), {})
    assert flags[0].check == "unique_key" and flags[0].severity == "structural"
    assert flags[0].source == "tabular"


def test_required_complete_flags_missing_values():
    df = pd.DataFrame({"x": [1, None]})
    flags = required_complete(_ctx(df, ["x"]), {})
    assert flags[0].check == "required_complete" and flags[0].value == "1"


def test_categoricals_flags_illegal_values_via_allowed():
    df = pd.DataFrame({"stage": [1, 2, 9]})
    flags = categoricals(_ctx(df, ["stage"]), {"spec": {"allowed": [1, 2, 3]}, "base_dir": "."})
    assert flags[0].check == "allowed"


def test_exclusive_flags_flags_cooccurrence():
    df = pd.DataFrame({"a": [1, 0], "b": [1, 0]})
    flags = exclusive_flags(_ctx(df, ["a", "b"]), {})
    assert flags[0].check == "exclusive_flags" and flags[0].subject == "a+b"


def test_type_conformance_flags_wrong_dtype():
    df = pd.DataFrame({"n": ["x", "y"]})
    flags = type_conformance(_ctx(df, ["n"]), {"expected": "numeric"})
    assert flags[0].check == "type_conformance" and flags[0].severity == "structural"

import pandas as pd
import pytest
from science_qa.selectors import SelectorError, resolve_columns

DF = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0], "label": ["x", "y"]})


def test_dtype_numeric_selects_numeric_columns():
    assert resolve_columns({"dtype": "numeric"}, DF, column_sets={}) == ["a", "b"]


def test_dtype_all_selects_every_column():
    assert resolve_columns({"dtype": "all"}, DF, column_sets={}) == ["a", "b", "label"]


def test_explicit_names_list_preserves_order_and_validates():
    assert resolve_columns(["b", "a"], DF, column_sets={}) == ["b", "a"]
    with pytest.raises(SelectorError, match="missing"):
        resolve_columns(["a", "nope"], DF, column_sets={})


def test_regex_matches_column_names():
    assert resolve_columns({"regex": "^a$|label"}, DF, column_sets={}) == ["a", "label"]


def test_named_set_resolves_through_config_column_sets():
    cs = {"numeric": {"dtype": "numeric"}}
    assert resolve_columns({"named_set": "numeric"}, DF, column_sets=cs) == ["a", "b"]
    with pytest.raises(SelectorError, match="undeclared"):
        resolve_columns({"named_set": "ghost"}, DF, column_sets=cs)


def test_empty_resolution_returns_empty_list_not_error():
    assert resolve_columns({"regex": "zzz"}, DF, column_sets={}) == []


def test_unknown_selector_kind_errors():
    with pytest.raises(SelectorError, match="unknown selector"):
        resolve_columns({"bogus": 1}, DF, column_sets={})

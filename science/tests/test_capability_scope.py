from __future__ import annotations

from science_tool.datasets.capability_scope import (
    CAPABILITY_SCOPE_VALUES,
    TYPE_I_SCOPES,
    TYPE_II_SCOPES,
    VALID_SCOPES,
    is_valid_scope,
)


def test_valid_scopes_are_the_seven_derived_values() -> None:
    assert VALID_SCOPES == {
        "reference-substrate",
        "derived-product",
        "methodological",
        "model-system",
        "clinical-outcome",
        "epidemiological",
        "behavioral-instrument",
    }


def test_type_partition_is_a_disjoint_cover() -> None:
    assert TYPE_I_SCOPES.isdisjoint(TYPE_II_SCOPES)
    assert TYPE_I_SCOPES | TYPE_II_SCOPES == VALID_SCOPES


def test_every_value_has_a_nonempty_definition() -> None:
    assert set(CAPABILITY_SCOPE_VALUES) == VALID_SCOPES
    assert all(text.strip() for text in CAPABILITY_SCOPE_VALUES.values())


def test_is_valid_scope() -> None:
    assert is_valid_scope("clinical-outcome") is True
    assert is_valid_scope("bogus") is False
    assert is_valid_scope(None) is False
    assert is_valid_scope(7) is False

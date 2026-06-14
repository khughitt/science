"""Tests for the typed Data Resource schema models (Spec 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.datasets.schema import FieldConstraints, FieldQA, MissingValue


class TestFieldValueModels:
    def test_missing_value_bare_and_labelled(self) -> None:
        assert MissingValue(value="NA").label == ""
        assert MissingValue(value="-999", label="sensor error").label == "sensor error"

    def test_constraints_defaults(self) -> None:
        c = FieldConstraints()
        assert c.required is False and c.unique is False
        assert c.minimum is None and c.enum is None

    def test_constraints_bounds_accept_str_int_float(self) -> None:
        c = FieldConstraints(minimum=0, maximum=1.0, exclusiveMinimum="2020-01-01")
        assert c.minimum == 0 and c.maximum == 1.0 and c.exclusiveMinimum == "2020-01-01"

    def test_constraints_extra_allowed(self) -> None:
        c = FieldConstraints.model_validate({"required": True, "futureProp": 7})
        assert c.required is True

    def test_enum_present_must_be_non_empty(self) -> None:
        FieldConstraints(enum=["a"])  # ok
        with pytest.raises(ValidationError, match="enum"):
            FieldConstraints(enum=[])

    def test_field_qa_defaults_and_closed_namespace(self) -> None:
        assert FieldQA().low_variance is False
        with pytest.raises(ValidationError):
            FieldQA.model_validate({"low_varianse": True})  # typo rejected (extra=forbid)

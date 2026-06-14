"""Tests for the typed Data Resource schema models (Spec 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.datasets.schema import FieldConstraints, FieldQA, FieldSpec, ForeignKey, MissingValue


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


class TestFieldSpec:
    def test_default_type_is_any(self) -> None:
        f = FieldSpec(name="x")
        assert f.type == "any"          # DP v2: omitted type ⇒ any, NOT string
        assert f.constraints.required is False
        assert f.qa.low_variance is False
        assert f.missingValues is None

    def test_field_level_missing_values_accepted(self) -> None:
        f = FieldSpec.model_validate({"name": "x", "type": "number", "missingValues": ["NA"]})
        assert f.missingValues == ["NA"]

    def test_bounds_require_numeric_or_temporal_type(self) -> None:
        FieldSpec(name="plddt", type="number", constraints={"minimum": 0, "maximum": 100})  # ok
        FieldSpec(name="d", type="date", constraints={"minimum": "2020-01-01"})              # ok
        with pytest.raises(ValidationError, match="numeric or temporal"):
            FieldSpec(name="s", type="string", constraints={"minimum": 0})

    def test_qa_stats_require_numeric_or_boolean_type(self) -> None:
        FieldSpec(name="n", type="integer", qa={"low_variance": True})                       # ok
        FieldSpec(name="b", type="boolean", qa={"zero_fraction": True})                      # ok
        with pytest.raises(ValidationError, match="integer/number/boolean"):
            FieldSpec(name="s", type="string", qa={"low_variance": True})

    def test_field_extra_allowed(self) -> None:
        f = FieldSpec.model_validate({"name": "x", "title": "X", "description": "d"})
        assert f.name == "x"


class TestForeignKey:
    def test_single_string_form(self) -> None:
        fk = ForeignKey.model_validate({"fields": "uniprot_id", "reference": {"resource": "proteins", "fields": "id"}})
        assert fk.fields == "uniprot_id"
        assert fk.reference.resource == "proteins"

    def test_self_reference_default_resource(self) -> None:
        fk = ForeignKey.model_validate({"fields": "parent_id", "reference": {"fields": "id"}})
        assert fk.reference.resource == ""          # "" ⇒ self

    def test_list_form_matched_cardinality(self) -> None:
        fk = ForeignKey.model_validate(
            {"fields": ["a", "b"], "reference": {"resource": "r", "fields": ["x", "y"]}}
        )
        assert fk.fields == ["a", "b"]

    def test_cardinality_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cardinality"):
            ForeignKey.model_validate(
                {"fields": ["a", "b"], "reference": {"resource": "r", "fields": "x"}}
            )

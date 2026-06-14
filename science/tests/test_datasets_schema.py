"""Tests for the typed Data Resource schema models (Spec 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.datasets.schema import FieldConstraints, FieldQA, FieldSpec, ForeignKey, MissingValue, TableQA, TableSchema


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


def _fields(*names: str) -> list[dict]:
    return [{"name": n} for n in names]


class TestTableSchemaShape:
    def test_minimal(self) -> None:
        t = TableSchema.model_validate({"fields": _fields("a", "b")})
        assert [f.name for f in t.fields] == ["a", "b"]
        assert t.uniqueKeys is None                 # absent
        assert t.missingValues == [""]              # DP v2 default
        assert t.qa.exclusive_flags == []

    def test_table_qa_closed_namespace(self) -> None:
        with pytest.raises(ValidationError):
            TableQA.model_validate({"exclusive_flagz": []})

    def test_unique_keys_absent_vs_empty(self) -> None:
        with pytest.raises(ValidationError, match="uniqueKeys.*non-empty"):
            TableSchema.model_validate({"fields": _fields("a"), "uniqueKeys": []})

    def test_unique_keys_inner_group_non_empty(self) -> None:
        with pytest.raises(ValidationError, match="group must be non-empty"):
            TableSchema.model_validate({"fields": _fields("a"), "uniqueKeys": [[]]})

    def test_missing_values_must_be_unique(self) -> None:
        TableSchema.model_validate({"fields": _fields("a"), "missingValues": ["", "NA"]})  # ok
        with pytest.raises(ValidationError, match="unique"):
            TableSchema.model_validate({"fields": _fields("a"), "missingValues": ["NA", "NA"]})

    def test_duplicate_field_names_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate field name"):
            TableSchema.model_validate({"fields": _fields("a", "a")})


class TestTableSchemaReferences:
    def test_primary_key_must_reference_known_field(self) -> None:
        TableSchema.model_validate({"fields": _fields("id"), "primaryKey": "id"})  # ok
        with pytest.raises(ValidationError, match="primaryKey references unknown"):
            TableSchema.model_validate({"fields": _fields("id"), "primaryKey": "nope"})

    def test_unique_keys_reference_known_fields(self) -> None:
        with pytest.raises(ValidationError, match="uniqueKeys references unknown"):
            TableSchema.model_validate({"fields": _fields("a"), "uniqueKeys": [["a", "b"]]})

    def test_foreign_key_local_field_must_exist(self) -> None:
        with pytest.raises(ValidationError, match="unknown local field"):
            TableSchema.model_validate(
                {"fields": _fields("a"),
                 "foreignKeys": [{"fields": "b", "reference": {"resource": "r", "fields": "x"}}]}
            )

    def test_exclusive_flags_reference_known_fields(self) -> None:
        with pytest.raises(ValidationError, match="exclusive_flags references unknown"):
            TableSchema.model_validate(
                {"fields": [{"name": "is_a", "type": "boolean"}],
                 "qa": {"exclusive_flags": [["is_a", "is_b"]]}}
            )

    def test_exclusive_flags_require_flag_typed_fields(self) -> None:
        TableSchema.model_validate(
            {"fields": [{"name": "is_a", "type": "boolean"}, {"name": "is_b", "type": "integer"}],
             "qa": {"exclusive_flags": [["is_a", "is_b"]]}}
        )  # ok
        with pytest.raises(ValidationError, match="must be boolean/integer"):
            TableSchema.model_validate(
                {"fields": [{"name": "is_a", "type": "boolean"}, {"name": "s", "type": "string"}],
                 "qa": {"exclusive_flags": [["is_a", "s"]]}}
            )

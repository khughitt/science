from pathlib import Path

import pytest
from science_qa.compile import CompileError, schema_to_config


def _resource(schema: dict, name="obs", path="obs.csv") -> dict:
    return {"name": name, "path": path, "schema": schema}


def _pkg(*resources: dict) -> dict:
    return {"name": "p", "resources": list(resources)}


class TestNativeMapping:
    def test_required_and_unique_and_type(self):
        res = _resource({"fields": [
            {"name": "id", "type": "integer", "constraints": {"required": True, "unique": True}},
            {"name": "label", "type": "string"},
        ]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.required_complete == ["id"]
        assert cfg.unique_keys == [["id"]]
        assert cfg.expected_types == {"id": "numeric", "label": "non-numeric"}
        assert cfg.base_dir == Path("/pkg")

    def test_type_any_produces_no_conformance_entry(self):
        res = _resource({"fields": [{"name": "x"}, {"name": "y", "type": "any"}]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.expected_types == {}

    def test_bounds_and_enum(self):
        res = _resource({"fields": [
            {"name": "p", "type": "number", "constraints": {"minimum": 0, "maximum": 100}},
            {"name": "grade", "type": "string", "constraints": {"enum": ["a", "b"]}},
        ]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.bounds == {"p": {"minimum": 0, "maximum": 100}}
        assert cfg.categoricals == {"grade": {"allowed": ["a", "b"]}}

    def test_primary_key_and_unique_keys_groups(self):
        res = _resource({"fields": [{"name": "a"}, {"name": "b"}, {"name": "c"}],
                         "primaryKey": ["a", "b"], "uniqueKeys": [["c"]]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert ["a", "b"] in cfg.unique_keys and ["c"] in cfg.unique_keys

    def test_missing_values_normalized_and_empty_dropped(self):
        res = _resource({"fields": [{"name": "x"}],
                         "missingValues": ["", "NA", {"value": "-999", "label": "sensor"}]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.missing_sentinels == ["NA", "-999"]

    def test_missing_schema_or_path_errors(self):
        with pytest.raises(CompileError, match="schema"):
            schema_to_config({"name": "o", "path": "o.csv"}, Path("/pkg"), _pkg())
        with pytest.raises(CompileError, match="path"):
            schema_to_config({"name": "o", "schema": {"fields": []}}, Path("/pkg"), _pkg())

    def test_empty_schema_is_minimal_not_crash(self):
        res = _resource({"fields": []})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.program == "" and cfg.required_complete == [] and cfg.bounds == {}

    def test_numeric_and_iso_date_bounds_accepted(self):
        res = _resource({"fields": [
            {"name": "p", "type": "number", "constraints": {"minimum": 0}},
            {"name": "d", "type": "date", "constraints": {"maximum": "2020-01-01"}},
        ]})
        cfg = schema_to_config(res, Path("/pkg"), _pkg(res))
        assert cfg.bounds == {"p": {"minimum": 0}, "d": {"maximum": "2020-01-01"}}

    def test_malformed_bound_value_is_compile_error(self):
        # descriptor-only: a string bound that is neither a number nor a parseable date
        res = _resource({"fields": [{"name": "p", "type": "number",
                                     "constraints": {"minimum": "not-a-date"}}]})
        with pytest.raises(CompileError, match="parseable ISO date"):
            schema_to_config(res, Path("/pkg"), _pkg(res))

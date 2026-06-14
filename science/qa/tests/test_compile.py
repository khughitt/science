from pathlib import Path

import pytest
from science_qa.compile import CompileError, merge_configs, schema_to_config
from science_qa.config import QAConfig


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


class TestForeignKeys:
    def test_single_column_fk_resolves_to_allowed_from(self):
        proteins = _resource({"fields": [{"name": "id"}]}, name="proteins", path="proteins.csv")
        edges = _resource(
            {"fields": [{"name": "src"}],
             "foreignKeys": [{"fields": "src", "reference": {"resource": "proteins", "fields": "id"}}]},
            name="edges", path="edges.csv",
        )
        cfg = schema_to_config(edges, Path("/pkg"), _pkg(proteins, edges))
        assert cfg.categoricals == {"src": {"allowed_from": "proteins.csv#id"}}

    def test_self_reference_points_at_own_path(self):
        tree = _resource(
            {"fields": [{"name": "id"}, {"name": "parent"}],
             "foreignKeys": [{"fields": "parent", "reference": {"fields": "id"}}]},
            name="tree", path="tree.csv",
        )
        cfg = schema_to_config(tree, Path("/pkg"), _pkg(tree))
        assert cfg.categoricals == {"parent": {"allowed_from": "tree.csv#id"}}

    def test_composite_fk_rejected(self):
        res = _resource(
            {"fields": [{"name": "a"}, {"name": "b"}],
             "foreignKeys": [{"fields": ["a", "b"], "reference": {"resource": "t", "fields": ["x", "y"]}}]},
        )
        with pytest.raises(CompileError, match="composite foreignKey"):
            schema_to_config(res, Path("/pkg"), _pkg(res))

    def test_unknown_target_resource_rejected(self):
        res = _resource(
            {"fields": [{"name": "src"}],
             "foreignKeys": [{"fields": "src", "reference": {"resource": "ghost", "fields": "id"}}]},
        )
        with pytest.raises(CompileError, match="unknown resource"):
            schema_to_config(res, Path("/pkg"), _pkg(res))

    def test_unknown_target_field_rejected(self):
        proteins = _resource({"fields": [{"name": "id"}]}, name="proteins", path="proteins.csv")
        edges = _resource(
            {"fields": [{"name": "src"}],
             "foreignKeys": [{"fields": "src", "reference": {"resource": "proteins", "fields": "nope"}}]},
            name="edges", path="edges.csv",
        )
        with pytest.raises(CompileError, match="reference field"):
            schema_to_config(edges, Path("/pkg"), _pkg(proteins, edges))


class TestMerge:
    def test_program_scalar_runknob_wins(self):
        contract = QAConfig(program="")
        runknobs = QAConfig(program="tabular")
        assert merge_configs(contract, runknobs).program == "tabular"

    def test_dict_union_with_runknob_override(self):
        contract = QAConfig(program="", bounds={"x": {"minimum": 0}}, categoricals={"g": {"allowed": ["a"]}})
        runknobs = QAConfig(program="", bounds={"y": {"maximum": 9}}, categoricals={"g": {"allowed": ["b"]}})
        merged = merge_configs(contract, runknobs)
        assert merged.bounds == {"x": {"minimum": 0}, "y": {"maximum": 9}}
        assert merged.categoricals == {"g": {"allowed": ["b"]}}  # runknob overrides same key

    def test_runknob_only_fields_overlay(self):
        contract = QAConfig(program="", base_dir=Path("/pkg"))
        runknobs = QAConfig(program="", polarity=["x"], project_local=["m:c"])
        merged = merge_configs(contract, runknobs)
        assert merged.polarity == ["x"] and merged.project_local == ["m:c"]
        assert merged.base_dir == Path("/pkg")  # contract base_dir (allowed_from resolves against package)

    def test_list_union_dedupes(self):
        # ["a"] and required "a" both appear in contract AND runknobs -> deduped, order kept
        contract = QAConfig(program="", required_complete=["a"], unique_keys=[["a"]])
        runknobs = QAConfig(program="", required_complete=["a", "b"], unique_keys=[["a"], ["b"]])
        merged = merge_configs(contract, runknobs)
        assert merged.required_complete == ["a", "b"]
        assert merged.unique_keys == [["a"], ["b"]]  # the duplicate ["a"] group collapsed

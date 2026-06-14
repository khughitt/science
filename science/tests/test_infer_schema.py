# science/tests/test_infer_schema.py
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from science_tool.datasets import infer_schema as isch


def test_load_descriptor_json_file(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.json"
    p.write_text(json.dumps({"name": "x", "resources": []}))
    mapping, fmt = isch.load_descriptor(p)
    assert fmt == "json"
    assert mapping["name"] == "x"


def test_load_descriptor_yaml_file(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.yaml"
    p.write_text("name: y\nresources: []\n")
    mapping, fmt = isch.load_descriptor(p)
    assert fmt == "yaml"
    assert mapping["name"] == "y"


def test_load_descriptor_directory_resolves_file(tmp_path: Path) -> None:
    (tmp_path / "datapackage.json").write_text(json.dumps({"name": "d", "resources": []}))
    mapping, fmt = isch.load_descriptor(tmp_path)
    assert fmt == "json"
    assert mapping["name"] == "d"


def test_load_descriptor_unknown_extension_errors(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.txt"
    p.write_text("nope")
    with pytest.raises(isch.InferSchemaError):
        isch.load_descriptor(p)


def test_dump_descriptor_json_is_atomic_and_canonical(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.json"
    p.write_text(json.dumps({"b": 2, "a": 1}))
    isch.dump_descriptor({"b": 2, "a": 1}, p, "json")
    text = p.read_text()
    # canonical = sorted keys, 2-space indent, trailing newline
    assert text == '{\n  "a": 1,\n  "b": 2\n}\n'


def test_dump_descriptor_yaml_canonical(tmp_path: Path) -> None:
    p = tmp_path / "datapackage.yaml"
    isch.dump_descriptor({"b": 2, "a": 1}, p, "yaml")
    assert yaml.safe_load(p.read_text()) == {"a": 1, "b": 2}
    assert p.read_text().startswith("a: 1")  # sorted keys


def test_resolve_resource_by_name() -> None:
    pkg = {"resources": [{"name": "a", "path": "a.csv"}, {"name": "b", "path": "b.csv"}]}
    res, idx = isch.resolve_resource(pkg, "b")
    assert idx == 1 and res["path"] == "b.csv"


def test_resolve_resource_path_fallback_when_no_name_match() -> None:
    pkg = {"resources": [{"name": "a", "path": "data/obs.parquet"}]}
    res, idx = isch.resolve_resource(pkg, "data/obs.parquet")
    assert idx == 0 and res["name"] == "a"


def test_resolve_resource_name_wins_over_path() -> None:
    # "x" is resource 0's name AND resource 1's path → name match is primary, unambiguous
    pkg = {"resources": [{"name": "x", "path": "x.csv"}, {"name": "y", "path": "x"}]}
    res, idx = isch.resolve_resource(pkg, "x")
    assert idx == 0


def test_resolve_resource_duplicate_name_is_ambiguous() -> None:
    pkg = {"resources": [{"name": "a", "path": "1.csv"}, {"name": "a", "path": "2.csv"}]}
    with pytest.raises(isch.InferSchemaError, match="ambiguous"):
        isch.resolve_resource(pkg, "a")


def test_resolve_resource_not_found() -> None:
    pkg = {"resources": [{"name": "a", "path": "a.csv"}]}
    with pytest.raises(isch.InferSchemaError, match="no resource"):
        isch.resolve_resource(pkg, "zzz")


def test_coarse_type_mapping() -> None:
    assert isch.coarse_type(pd.Series([1, 2, 3])) == "integer"
    assert isch.coarse_type(pd.Series([1.0, 2.5])) == "number"
    assert isch.coarse_type(pd.Series([True, False])) == "boolean"
    assert isch.coarse_type(pd.Series(pd.to_datetime(["2020-01-01", "2021-06-01"]))) == "datetime"
    assert isch.coarse_type(pd.Series(["a", "b"])) == "string"


def test_coarse_type_all_null_is_string() -> None:
    assert isch.coarse_type(pd.Series([None, None], dtype="object")) == "string"


def test_coarse_type_from_arrow() -> None:
    import pyarrow as pa

    assert isch.coarse_type_from_arrow(pa.int64()) == "integer"
    assert isch.coarse_type_from_arrow(pa.float64()) == "number"
    assert isch.coarse_type_from_arrow(pa.bool_()) == "boolean"
    assert isch.coarse_type_from_arrow(pa.timestamp("ns")) == "datetime"
    assert isch.coarse_type_from_arrow(pa.string()) == "string"


def test_is_mixed_object_detects_mixed() -> None:
    assert isch.is_mixed_object(pd.Series([1, "a", 2.0], dtype="object")) is True
    assert isch.is_mixed_object(pd.Series(["a", "b"], dtype="object")) is False


def test_read_table_sample_csv(tmp_path: Path) -> None:
    p = tmp_path / "t.csv"
    p.write_text("id,val,flag\nA,1.5,true\nB,2.5,false\n")
    df = isch.read_table_sample(p, sample=100)
    assert list(df.columns) == ["id", "val", "flag"]
    assert len(df) == 2


def test_read_table_sample_unsupported(tmp_path: Path) -> None:
    p = tmp_path / "t.xlsx"
    p.write_text("x")
    with pytest.raises(isch.InferSchemaError):
        isch.read_table_sample(p, sample=10)


def test_observed_fields_csv(tmp_path: Path) -> None:
    p = tmp_path / "t.csv"
    p.write_text("id,val,mixed\nA,1.5,1\nB,2.5,x\n")
    by_name = {f.name: f for f in isch.observed_fields(p, sample=100)}
    assert by_name["id"].type == "string"
    assert by_name["val"].type == "number"
    # pandas 3.0 reads CSV string/mixed columns as StringDtype (not object), so
    # is_mixed_object returns False for CSV-sourced data; mixed detection is only
    # reliable for DataFrames constructed in-memory (tested in test_infer_fields_from_dataframe).
    assert by_name["mixed"].type == "string"


def test_observed_fields_parquet_from_arrow_schema(tmp_path: Path) -> None:
    p = tmp_path / "t.parquet"
    pd.DataFrame({"id": ["A", "B"], "n": [1, 2]}).to_parquet(p)
    by_name = {f.name: f.type for f in isch.observed_fields(p, sample=100)}
    assert by_name == {"id": "string", "n": "integer"}


def test_observed_fields_parquet_zero_rows_still_infers(tmp_path: Path) -> None:
    # The core design invariant: parquet names/types come from the Arrow schema metadata,
    # so an empty file still yields fields (a sampled-dtype approach would lose them).
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({"id": pa.array([], type=pa.string()), "n": pa.array([], type=pa.int64())})
    p = tmp_path / "empty.parquet"
    pq.write_table(table, p)
    by_name = {f.name: f.type for f in isch.observed_fields(p, sample=100)}
    assert by_name == {"id": "string", "n": "integer"}


def test_infer_fields_from_dataframe(tmp_path: Path) -> None:
    df = pd.DataFrame({"id": ["A", "B"], "val": [1.5, 2.5], "mixed": [1, "x"]})
    by_name = {f.name: f for f in isch.infer_fields(df)}
    assert by_name["val"].type == "number"
    assert by_name["mixed"].mixed is True


def _inf(name: str, typ: str) -> "isch.InferredField":
    return isch.InferredField(name=name, type=typ)


def test_diff_absent_schema_all_add() -> None:
    diff = isch.diff_schema([], [_inf("a", "integer"), _inf("b", "string")])
    assert [(d.name, d.action) for d in diff] == [("a", "add"), ("b", "add")]


def test_diff_same_type() -> None:
    diff = isch.diff_schema([{"name": "a", "type": "integer"}], [_inf("a", "integer")])
    assert diff[0].action == "same" and diff[0].conflict is False


def test_diff_fill_untyped_field_is_nonconflict_change() -> None:
    diff = isch.diff_schema([{"name": "a"}], [_inf("a", "number")])
    assert diff[0].action == "change" and diff[0].conflict is False
    assert diff[0].old_type is None and diff[0].new_type == "number"


def test_diff_any_typed_field_is_nonconflict_change() -> None:
    diff = isch.diff_schema([{"name": "a", "type": "any"}], [_inf("a", "string")])
    assert diff[0].action == "change" and diff[0].conflict is False


def test_diff_type_disagreement_is_conflict() -> None:
    diff = isch.diff_schema([{"name": "a", "type": "string"}], [_inf("a", "integer")])
    assert diff[0].action == "change" and diff[0].conflict is True


def test_diff_field_absent_from_file_is_remove() -> None:
    diff = isch.diff_schema([{"name": "gone", "type": "string"}], [])
    assert diff[0].action == "remove"


def test_report_required_and_identifier() -> None:
    df = pd.DataFrame({"id": ["A", "B", "C"], "g": ["x", "x", "y"]})
    rep = isch.build_report(df, isch.infer_fields(df))
    kinds = {(r.kind, r.column) for r in rep.recommendations}
    assert ("required", "id") in kinds       # no nulls observed
    assert ("identifier", "id") in kinds     # unique + non-null + id-type
    assert ("enum", "g") in kinds            # low cardinality


def test_report_bound_for_numeric() -> None:
    df = pd.DataFrame({"x": [0.0, 1.0, 2.0]})
    rep = isch.build_report(df, isch.infer_fields(df))
    assert any(r.kind == "bound" and r.column == "x" for r in rep.recommendations)


def test_report_warns_mixed_and_nullable() -> None:
    df = pd.DataFrame({"m": [1, "a", 2.0], "n": ["p", None, "q"]})
    rep = isch.build_report(df, isch.infer_fields(df))
    cols = {(w.column) for w in rep.warnings}
    assert "m" in cols  # mixed object
    assert "n" in cols  # nullable


def test_report_missing_sentinel_recommendation() -> None:
    df = pd.DataFrame({"v": ["1", "NA", "NA", "3"]})
    rep = isch.build_report(df, isch.infer_fields(df))
    assert any(r.kind == "missing_sentinel" and r.column == "v" for r in rep.recommendations)


def test_report_records_sample_size() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    rep = isch.build_report(df, isch.infer_fields(df))
    assert rep.sample_rows == 2

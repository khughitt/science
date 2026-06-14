# science/tests/test_infer_schema.py
from __future__ import annotations

import json
from pathlib import Path

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

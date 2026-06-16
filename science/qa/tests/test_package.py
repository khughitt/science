from pathlib import Path

import pytest
from science_qa.package import load_package


def test_load_json(tmp_path):
    (tmp_path / "datapackage.json").write_text('{"name": "p", "resources": []}')
    mapping, base = load_package(tmp_path / "datapackage.json")
    assert mapping["name"] == "p" and base == tmp_path


def test_load_yaml(tmp_path):
    (tmp_path / "datapackage.yaml").write_text("name: p\nresources: []\n")
    mapping, base = load_package(tmp_path / "datapackage.yaml")
    assert mapping["name"] == "p" and base == tmp_path


def test_unquoted_iso_date_stays_string(tmp_path):
    # the false-CompileError regression: a YAML date bound must remain a str
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: r\n    path: r.csv\n    schema:\n      fields:\n"
        "        - name: d\n          type: date\n"
        "          constraints: {maximum: 2020-01-01}\n")
    mapping, _ = load_package(tmp_path / "datapackage.yaml")
    bound = mapping["resources"][0]["schema"]["fields"][0]["constraints"]["maximum"]
    assert bound == "2020-01-01" and isinstance(bound, str)


def test_unknown_extension_rejected(tmp_path):
    (tmp_path / "datapackage.txt").write_text("nope")
    with pytest.raises(ValueError, match="extension"):
        load_package(tmp_path / "datapackage.txt")

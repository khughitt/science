from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from science_tool.datasets import qa as _qa


def _pkg(tmp_path: Path, *, minimum: int | None = None) -> Path:
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(tmp_path / "a.parquet")
    constraints = f"          constraints: {{minimum: {minimum}}}\n" if minimum is not None else ""
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n" + constraints)
    return tmp_path


def test_resolve_directory_to_descriptor(tmp_path):
    _pkg(tmp_path)
    assert _qa._resolve_descriptor(tmp_path).name == "datapackage.yaml"


def test_resolve_descriptor_file_directly(tmp_path):
    _pkg(tmp_path)
    desc = tmp_path / "datapackage.yaml"
    assert _qa._resolve_descriptor(desc) == desc


def test_resolve_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="descriptor"):
        _qa._resolve_descriptor(tmp_path)


def test_exit_zero_when_clean(tmp_path):
    _pkg(tmp_path)  # no minimum -> no structural flag
    result, code = _qa.run_package_qa(tmp_path)
    assert code == 0 and result.package_structural_failed is False


def test_exit_one_on_structural(tmp_path):
    _pkg(tmp_path, minimum=0)  # -1.0 violates minimum 0
    result, code = _qa.run_package_qa(tmp_path)
    assert code == 1 and result.package_structural_failed is True


def test_no_strict_suppresses_exit_one(tmp_path):
    _pkg(tmp_path, minimum=0)
    _result, code = _qa.run_package_qa(tmp_path, no_strict=True)
    assert code == 0


def test_unknown_resource_raises_compile_error(tmp_path):
    from science_qa.compile import CompileError
    _pkg(tmp_path)
    with pytest.raises(CompileError):
        _qa.run_package_qa(tmp_path, resource="ghost")


def test_json_dict_matches_persisted_report(tmp_path):
    from science_qa.runner import package_report_dict
    _pkg(tmp_path, minimum=0)
    out = tmp_path / "out"
    result, _code = _qa.run_package_qa(tmp_path, report_dir=out)
    stdout_json = json.dumps(package_report_dict(result), indent=2, sort_keys=True) + "\n"
    assert stdout_json == (out / "qa_report.json").read_text()


def test_loader_drift_guard_iso_bound(tmp_path):
    # science_qa.load_package and science_tool.infer_schema.load_descriptor must parse an
    # unquoted ISO bound to the identical str (no PyYAML timestamp coercion drift).
    from science_qa.package import load_package
    from science_tool.datasets.infer_schema import load_descriptor
    (tmp_path / "datapackage.yaml").write_text(
        "name: p\nresources:\n  - name: r\n    path: r.csv\n    schema:\n      fields:\n"
        "        - name: d\n          type: date\n          constraints: {maximum: 2020-01-01}\n")
    qa_map, _ = load_package(tmp_path / "datapackage.yaml")
    tool_map, _ = load_descriptor(tmp_path / "datapackage.yaml")
    qa_bound = qa_map["resources"][0]["schema"]["fields"][0]["constraints"]["maximum"]
    tool_bound = tool_map["resources"][0]["schema"]["fields"][0]["constraints"]["maximum"]
    assert qa_bound == tool_bound == "2020-01-01"

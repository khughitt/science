# science/tests/test_data_audit_fix_datapackage.py
"""Datapackage resource-path rewrite on relocation."""
import subprocess
from pathlib import Path

import yaml

from science_tool.data_audit import audit_project
from science_tool.data_audit_fix import apply_fixes


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _write(root: Path, rel: str, content: bytes) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def _resolves_to(root: Path, descriptor_rel: str, dp: dict, payload_rel: str) -> bool:
    base = (root / descriptor_rel).parent / dp.get("basepath", ".")
    target = (base / dp["resources"][0]["path"]).resolve()
    return target == (root / payload_rel).resolve()


def test_rewrite_preserves_resolution_no_basepath(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)  # payload stays
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           yaml.safe_dump({
               "name": "exp1-pkg",
               "resources": [{"name": "matrix", "path": "matrix.feather"}],
           }).encode())
    apply_fixes(tmp_path, audit_project(tmp_path))
    moved = tmp_path / "results/exp1/datapackage.yaml"
    assert moved.exists()
    dp = yaml.safe_load(moved.read_text())
    # payload did NOT move; descriptor now reaches back into data/.
    assert (tmp_path / "data/processed/exp1/matrix.feather").exists()
    assert _resolves_to(tmp_path, "results/exp1/datapackage.yaml", dp,
                        "data/processed/exp1/matrix.feather")


def test_rewrite_preserves_existing_basepath(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)
    _write(tmp_path, "data/processed/exp1/out/datapackage.yaml",
           yaml.safe_dump({
               "name": "exp1-r1-out",
               "basepath": "..",
               "resources": [{"name": "matrix", "path": "matrix.feather"}],
           }).encode())
    apply_fixes(tmp_path, audit_project(tmp_path))
    moved = tmp_path / "results/exp1/out/datapackage.yaml"
    assert moved.exists()
    dp = yaml.safe_load(moved.read_text())
    assert dp["basepath"] == ".."  # preserved
    assert _resolves_to(tmp_path, "results/exp1/out/datapackage.yaml", dp,
                        "data/processed/exp1/matrix.feather")


def test_absolute_resource_path_flags(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           yaml.safe_dump({
               "name": "x",
               "resources": [{"name": "m", "path": "/abs/matrix.feather"}],
           }).encode())
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.path.endswith("datapackage.yaml")][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "data/processed/exp1/datapackage.yaml").exists()  # not moved


def test_json_descriptor_stays_json(tmp_path: Path):
    import json as _json
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/matrix.feather", b"\x00" * 8)
    _write(tmp_path, "data/processed/exp1/datapackage.json",
           _json.dumps({"name": "x",
                        "resources": [{"name": "m", "path": "matrix.feather"}]}).encode())
    apply_fixes(tmp_path, audit_project(tmp_path))
    moved = tmp_path / "results/exp1/datapackage.json"
    assert moved.exists()
    dp = _json.loads(moved.read_text())  # still valid JSON, not YAML
    assert _resolves_to(tmp_path, "results/exp1/datapackage.json", dp,
                        "data/processed/exp1/matrix.feather")


def test_malformed_resource_entry_flags(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           b"name: x\nresources:\n- just-a-string\n")
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.path.endswith("datapackage.yaml")][0]
    assert o.performed is False and o.action == "flag"  # FLAG, did not crash


def test_basepath_escaping_repo_flags(tmp_path: Path):
    # Descriptor one level under data/processed; basepath "../../../.." escapes the repo.
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           yaml.safe_dump({
               "name": "x",
               "basepath": "../../../..",
               "resources": [{"name": "m", "path": "matrix.feather"}],
           }).encode())
    outcomes = apply_fixes(tmp_path, audit_project(tmp_path))
    o = [o for o in outcomes if o.violation.path.endswith("datapackage.yaml")][0]
    assert o.performed is False and o.action == "flag"
    assert (tmp_path / "data/processed/exp1/datapackage.yaml").exists()  # not moved


def test_flagged_datapackage_leaves_no_empty_results_dir(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/datapackage.yaml",
           yaml.safe_dump({
               "name": "x",
               "resources": [{"name": "m", "path": "/abs/matrix.feather"}],
           }).encode())
    apply_fixes(tmp_path, audit_project(tmp_path))
    assert not (tmp_path / "results" / "exp1").exists()  # no empty dir littered

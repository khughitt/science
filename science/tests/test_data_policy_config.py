"""science.yaml data_policy block → DataPolicy resolution."""
from pathlib import Path

import pytest
import yaml

from science_tool.data_policy import DEFAULT_DATA_POLICY
from science_tool.project_config import (
    load_project_config,
    resolve_data_policy,
)


def _write_yaml(tmp_path: Path, body: dict) -> Path:
    body.setdefault("name", "Demo")
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")
    return tmp_path


def test_absent_block_resolves_to_default(tmp_path: Path):
    _write_yaml(tmp_path, {})
    cfg = load_project_config(tmp_path)
    assert cfg.data_policy is None
    assert resolve_data_policy(cfg) == DEFAULT_DATA_POLICY


def test_override_threshold_and_patterns(tmp_path: Path):
    _write_yaml(tmp_path, {
        "data_policy": {
            "record_patterns": ["RESULTS*.md"],
            "payload_extensions": [".feather"],
            "size_threshold": 256000,
        }
    })
    cfg = load_project_config(tmp_path)
    pol = resolve_data_policy(cfg)
    assert pol.size_threshold == 256000
    assert pol.record_patterns == ("RESULTS*.md",)
    assert pol.payload_extensions == (".feather",)


def test_unknown_field_rejected(tmp_path: Path):
    _write_yaml(tmp_path, {"data_policy": {"bogus": 1}})
    with pytest.raises(Exception):
        load_project_config(tmp_path)

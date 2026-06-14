# science/tests/test_descriptor_contract.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.datasets.schema import ResourceDescriptor, package_consistency_issues

CORPUS = Path(__file__).resolve().parents[1] / "fixtures" / "descriptor_contract"


def _fixtures() -> list[Path]:
    files = sorted(CORPUS.glob("*.json"))
    assert files, f"no contract fixtures found in {CORPUS}"
    return files


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.name)
def test_fixture_is_spec1_valid(path: Path) -> None:
    descriptor = ResourceDescriptor.model_validate(json.loads(path.read_text()))
    # single-resource self-consistency (FK self-references resolve within the one resource)
    assert package_consistency_issues([descriptor]) == []

# science/qa/tests/test_descriptor_contract.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_qa.compile import CompileError, schema_to_config

CORPUS = Path(__file__).resolve().parents[2] / "fixtures" / "descriptor_contract"

# The ONLY reasons a Spec-1-valid descriptor may fail to compile (design §7 allow-list).
DOCUMENTED_COMPILER_ONLY = {
    "composite_fk.json": "composite foreignKey not supported",
    "malformed_bound.json": "is neither a number nor a parseable ISO date",
}


def _fixtures() -> list[Path]:
    files = sorted(CORPUS.glob("*.json"))
    assert files, f"no contract fixtures found in {CORPUS}"
    return files


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.name)
def test_fixture_compiles_or_fails_for_documented_reason(path: Path) -> None:
    resource = json.loads(path.read_text())
    package = {"resources": [resource]}
    if path.name in DOCUMENTED_COMPILER_ONLY:
        expected = DOCUMENTED_COMPILER_ONLY[path.name]
        with pytest.raises(CompileError, match=expected):
            schema_to_config(resource, path.parent, package)
    else:
        cfg = schema_to_config(resource, path.parent, package)  # must not raise
        assert cfg is not None

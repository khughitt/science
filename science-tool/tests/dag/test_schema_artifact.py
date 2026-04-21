"""Drift guard: committed edges.schema.json == EdgesYamlFile.model_json_schema()."""

from __future__ import annotations

import json
from pathlib import Path

from science_tool.dag.schema import EdgesYamlFile

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "src" / "science_tool" / "dag" / "edges.schema.json"


def _canonical(obj: object) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def test_committed_schema_matches_pydantic_emit() -> None:
    emitted = EdgesYamlFile.model_json_schema()
    actual = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert actual == emitted, (
        f"Committed {SCHEMA_PATH.name} is out of sync with Pydantic. "
        f"Regenerate: `science-tool dag schema --output {SCHEMA_PATH}`"
    )


def test_committed_schema_canonical_formatted() -> None:
    # The on-disk file is canonically serialized (sorted keys, 2-space indent,
    # trailing newline). This catches accidental re-serialization without
    # canonicalization.
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    emitted = EdgesYamlFile.model_json_schema()
    assert text == _canonical(emitted), (
        f"Committed schema is not in canonical form. Regenerate: `science-tool dag schema --output {SCHEMA_PATH}`"
    )

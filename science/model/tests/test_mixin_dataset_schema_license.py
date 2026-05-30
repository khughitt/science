from __future__ import annotations

import json
from pathlib import Path

_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "model/src/science_model/schemas/mixin-dataset-1.0.json"
)


def test_mixin_dataset_schema_declares_license() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert "license" in schema["properties"]
    assert schema["properties"]["license"] == {"type": "string"}

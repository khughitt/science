"""The SECOND external manifest entry point, pinned so the two cannot silently diverge.

`science_model`'s `load_profile_manifest` and the tool's `_validate_manifest_shape` both reach
`ProfileManifest.model_validate` today. That is why one before-validator covers both -- and
exactly why it needs a test on THIS side: a future refactor that hand-rolls the tool-side parse
would leave the rejection covered by a model test that keeps passing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.entity_kinds import _validate_manifest_shape


def _manifest(**kind_extra: object) -> dict:
    return {
        "name": "local",
        "imports": [],
        "relation_kinds": [],
        "strictness": "typed-extension",
        "entity_kinds": [
            {
                "name": "widget",
                "canonical_prefix": "widget",
                "layer": "layer/local",
                "description": "d",
                **kind_extra,
            }
        ],
    }


def test_the_TOOL_side_loader_refuses_an_authored_schema_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="schema_closed"):
        _validate_manifest_shape(tmp_path / "manifest.yaml", _manifest(schema_closed=True))


def test_the_tool_side_loader_admits_an_ordinary_local_kind(tmp_path: Path) -> None:
    # The rejection must be about the RESERVED field, not about local kinds in general -- a check
    # that refuses everything would pass the test above while breaking `science kinds register`.
    _validate_manifest_shape(tmp_path / "manifest.yaml", _manifest(entity_class="reference"))


def test_registering_a_local_kind_still_works_end_to_end(tmp_path: Path) -> None:
    from science_tool.entity_kinds import register_local_kind

    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "demo"}), encoding="utf-8")
    assert register_local_kind(tmp_path, "widget", "reference") == "registered"

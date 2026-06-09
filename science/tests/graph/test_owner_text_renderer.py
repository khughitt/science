from __future__ import annotations

import yaml

from science_tool.graph.aggregate_retire import _STUB_BODY, _owner_text


def _split(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n")
    _, fm_block, body = text.split("---\n", 2)
    return yaml.safe_load(fm_block), body


def test_non_empty_description_becomes_body() -> None:
    text = _owner_text("concept:x", "concept", "X", "A definition.", None, promoted_from="a.yaml")
    fm, body = _split(text)
    assert fm == {"id": "concept:x", "type": "concept", "title": "X", "promoted_from": "a.yaml"}
    assert body == "\nA definition.\n"  # single blank line after frontmatter, then body + one newline


def test_empty_description_falls_back_to_stub_body() -> None:
    text = _owner_text("concept:x", "concept", "X", "", None, promoted_from="a.yaml")
    assert _STUB_BODY in text


def test_non_string_description_treated_as_absent() -> None:
    text = _owner_text("concept:x", "concept", "X", {"unexpected": "mapping"}, None, promoted_from="a.yaml")
    assert _STUB_BODY in text


def test_description_trailing_newlines_normalized_to_one() -> None:
    text = _owner_text("concept:x", "concept", "X", "Def.\n\n\n", None, promoted_from="a.yaml")
    _, body = _split(text)
    assert body == "\nDef.\n"


def test_profile_included_when_present() -> None:
    text = _owner_text("concept:x", "concept", "X", "Def.", "research", promoted_from="a.yaml")
    fm, _ = _split(text)
    assert fm["profile"] == "research"


def test_none_description_falls_back_to_stub_body() -> None:
    text = _owner_text("concept:x", "concept", "X", None, None, promoted_from="a.yaml")
    assert _STUB_BODY in text

from __future__ import annotations

import yaml

from science_tool.graph.aggregate_retire import _STUB_BODY, _owner_text


def _split(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n")
    _, fm_block, body = text.split("---\n", 2)
    return yaml.safe_load(fm_block), body


def _render(description: object, profile: object = None) -> str:
    """Render with fixed conformance fields so tests assert on identity/body only."""
    return _owner_text(
        "concept:x",
        "concept",
        "X",
        description,
        profile,
        status="active",
        created="2026-06-09",
        updated="2026-06-09",
        promoted_from="a.yaml",
    )


def test_non_empty_description_becomes_body() -> None:
    fm, body = _split(_render("A definition."))
    assert fm == {
        "id": "concept:x",
        "kind": "concept",
        "title": "X",
        "status": "active",
        "created": "2026-06-09",
        "updated": "2026-06-09",
        "promoted_from": "a.yaml",
    }
    assert body == "\nA definition.\n"  # single blank line after frontmatter, then body + one newline


def test_required_conformance_fields_are_present() -> None:
    fm, _ = _split(_render("Def."))
    # Mirrors entity_conformance._REQUIRED_FRONTMATTER — a promoted owner must be conformant.
    for field in ("id", "kind", "title", "status", "created", "updated"):
        assert field in fm, f"missing required frontmatter field {field!r}"


def test_empty_description_falls_back_to_stub_body() -> None:
    assert _STUB_BODY in _render("")


def test_non_string_description_treated_as_absent() -> None:
    assert _STUB_BODY in _render({"unexpected": "mapping"})


def test_description_trailing_newlines_normalized_to_one() -> None:
    _, body = _split(_render("Def.\n\n\n"))
    assert body == "\nDef.\n"


def test_profile_included_when_present() -> None:
    fm, _ = _split(_render("Def.", "research"))
    assert fm["profile"] == "research"


def test_none_description_falls_back_to_stub_body() -> None:
    assert _STUB_BODY in _render(None)

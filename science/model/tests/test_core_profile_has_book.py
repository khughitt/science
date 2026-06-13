from __future__ import annotations

from science_model.profiles import CORE_PROFILE


def test_core_profile_declares_book_kind() -> None:
    by_name = {k.name: k for k in CORE_PROFILE.entity_kinds}
    assert "book" in by_name, "book must be a core profile kind"
    book = by_name["book"]
    assert book.canonical_prefix == "book"
    assert book.layer == "layer/core"

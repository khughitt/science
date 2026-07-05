from __future__ import annotations

from science_model.lenses import LENS_BY_SLUG, LENS_SLUGS, is_valid_lens


def test_six_canonical_lenses() -> None:
    assert LENS_SLUGS == {
        "mechanism", "methodology", "population", "contrarian", "analogy", "temporal",
    }


def test_is_valid_lens() -> None:
    assert is_valid_lens("mechanism")
    assert not is_valid_lens("holistic")


def test_lens_metadata() -> None:
    assert LENS_BY_SLUG["temporal"].description.startswith("temporal")
    assert LENS_BY_SLUG["mechanism"].kind == "generative-analytical"

from __future__ import annotations

from science_model.licenses import (
    KNOWN_LICENSES,
    LICENSE_SENTINELS,
    is_recognized,
    suggest,
)


def test_known_licenses_include_common_data_licenses() -> None:
    for lic in ("CC-BY-4.0", "CC0-1.0", "ODbL-1.0", "MIT", "Apache-2.0"):
        assert lic in KNOWN_LICENSES


def test_sentinels_are_unknown_proprietary_custom() -> None:
    assert LICENSE_SENTINELS == frozenset({"unknown", "proprietary", "custom"})


def test_is_recognized_accepts_known_and_sentinels_case_sensitively() -> None:
    assert is_recognized("CC-BY-4.0") is True
    assert is_recognized("unknown") is True
    assert is_recognized("cc-by-4.0") is False  # wrong case -> not recognized (but suggestible)
    assert is_recognized("Totally Made Up") is False


def test_suggest_matches_case_and_separator_variants() -> None:
    assert suggest("cc-by-4.0") == "CC-BY-4.0"
    assert suggest("CC_BY_4.0") == "CC-BY-4.0"
    assert suggest("apache 2.0") == "Apache-2.0"


def test_suggest_returns_none_for_gibberish_and_empty() -> None:
    assert suggest("zzzzz") is None
    assert suggest("") is None

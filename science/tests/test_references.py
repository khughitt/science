from __future__ import annotations

from science_tool.references import format_authors


def test_format_authors_last_first_with_initials() -> None:
    raw = "Williams, Donald R. and Rast, Philippe and Buerkner, Paul-Christian"
    assert format_authors(raw) == "Williams DR, Rast P, Buerkner P-C"


def test_format_authors_first_last_and_jr() -> None:
    assert format_authors("Donald Williams") == "Williams D"
    assert format_authors("King, Jr, Martin Luther") == "King ML"


def test_format_authors_braced_corporate_is_literal() -> None:
    assert format_authors("{World Health Organization}") == "World Health Organization"


def test_format_authors_truncates_beyond_six() -> None:
    raw = " and ".join(f"Last{i}, First{i}" for i in range(1, 9))  # 8 authors
    assert format_authors(raw) == "Last1 F, Last2 F, Last3 F, et al."


def test_format_authors_empty() -> None:
    assert format_authors(None) == ""
    assert format_authors("") == ""

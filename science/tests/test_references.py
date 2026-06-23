from __future__ import annotations

from science_tool.bibliography import BibEntry
from science_tool.references import CONTRACT, SCHEMA_VERSION, format_authors, format_display, reference_record


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


def test_reference_record_rich() -> None:
    entry = BibEntry(
        key="Williams2018",
        entry_type="article",
        title="Bayesian Meta-Analysis",
        year=2018,
        url="https://osf.io/9n4zp/",
        author="Williams, Donald R. and Rast, Philippe",
        journal="PsyArXiv",
        volume="12",
        number="3",
        pages="45-67",
    )
    rec = reference_record(entry)
    assert rec["contract"] == CONTRACT
    assert rec["schema_version"] == SCHEMA_VERSION
    assert rec["id"] == "cite:Williams2018"
    assert rec["citekey"] == "Williams2018"
    assert rec["kind"] == "article"
    assert rec["issued"] == {"year": 2018}
    assert rec["container_title"] == "PsyArXiv"
    assert rec["authors"] == [
        {"family": "Williams", "given": "Donald R."},
        {"family": "Rast", "given": "Philippe"},
    ]
    assert rec["source"]["raw_author"] == "Williams, Donald R. and Rast, Philippe"
    assert rec["display"] == (
        "Williams DR, Rast P. Bayesian Meta-Analysis. PsyArXiv. 2018;12(3):45-67."
    )


def test_format_display_sparse_falls_back_to_citekey() -> None:
    entry = BibEntry(key="Williams2018", title="Bayesian Meta-Analysis", year=2018)
    assert format_display(entry) == "Williams2018. Bayesian Meta-Analysis. 2018."


def test_reference_record_kind_normalization() -> None:
    assert reference_record(BibEntry(key="X", entry_type="inproceedings"))["kind"] == "chapter"
    assert reference_record(BibEntry(key="X", entry_type="incollection"))["kind"] == "chapter"
    assert reference_record(BibEntry(key="X", entry_type="book"))["kind"] == "book"
    assert reference_record(BibEntry(key="X", entry_type="online"))["kind"] == "misc"

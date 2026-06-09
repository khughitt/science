from __future__ import annotations

from pathlib import Path

from science_tool.bibliography import BibEntry, load_bib_entries


def _write_bib(root: Path, text: str) -> None:
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "references.bib").write_text(text, encoding="utf-8")


def test_load_bib_entries_parses_fields_and_gates_on_balance(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        "@article{Smith2024,\n"
        "  title = {The {DNA} story},\n"  # nested braces must NOT truncate
        "  year = {2024},\n"
        "  doi = {10.1/x},\n"
        "}\n\n"
        "@article{Broken2020,\n"
        "  title = {Truncated without a close brace\n",  # unbalanced -> excluded
    )
    entries = load_bib_entries(tmp_path)
    assert isinstance(entries["Smith2024"], BibEntry)
    assert entries["Smith2024"].title == "The {DNA} story"
    assert entries["Smith2024"].year == 2024
    assert entries["Smith2024"].doi == "10.1/x"
    assert entries["Smith2024"].url is None  # absent field -> None
    assert "Broken2020" not in entries  # unbalanced entry contributes no key


def test_load_bib_entries_quoted_and_bare_forms(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        '@article{Jones2019,\n  title = "Quoted Title",\n  year = 2019,\n}\n',
    )
    assert load_bib_entries(tmp_path)["Jones2019"].title == "Quoted Title"
    assert load_bib_entries(tmp_path)["Jones2019"].year == 2019


def test_load_bib_entries_out_of_range_year_clamped_to_none(tmp_path: Path) -> None:
    # PaperEntity.year is ge=1800/le=2200. A balanced entry with an out-of-range
    # year must STILL be admitted (it is node-producing) but with year=None, so the
    # synthesized PaperEntity validates and the "backed" invariant holds.
    _write_bib(tmp_path, "@article{Old1600,\n  title = {Ancient},\n  year = {1600},\n}\n")
    entries = load_bib_entries(tmp_path)
    assert "Old1600" in entries  # still backed (node-producing)
    assert entries["Old1600"].year is None  # clamped, cannot break validation


def test_load_bib_entries_absent_file_is_empty(tmp_path: Path) -> None:
    assert load_bib_entries(tmp_path) == {}


def test_load_bib_entries_ignores_field_name_embedded_in_other_value(tmp_path: Path) -> None:
    # A free-text note value mentioning "doi = {...}" must NOT shadow the real doi field.
    _write_bib(
        tmp_path,
        "@article{Note2024,\n  note = {see doi = {10.x/fake} in the supplement},\n  doi = {10.1/real},\n}\n",
    )
    assert load_bib_entries(tmp_path)["Note2024"].doi == "10.1/real"

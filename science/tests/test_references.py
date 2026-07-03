from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from science_tool.bibliography import BibEntry
from science_tool.markdown_utils import UnterminatedHtmlCommentError
from science_tool.references import (
    CONTRACT,
    SCHEMA_VERSION,
    DuplicateCitekeyError,
    MarkdownPayload,
    UnresolvedCitationError,
    UnsupportedCitationSyntaxError,
    build_reference_bundle,
    format_authors,
    format_display,
    parse_citations,
    reference_record,
    validate_exported_markdown,
)

_CORPUS = Path(__file__).parent / "fixtures" / "citation_grammar_v1.json"
# Drift guard: the identical constant lives in Labnote's test/citations.test.js.
# Both repos hash their copy of the corpus against this value, so a hand-edit to
# either copy fails CI until the corpus is re-synced and the constant updated in
# both places (deliberate, visible). Fill in with the Step 1b command output.
CITATION_GRAMMAR_V1_SHA256 = "65329d96d10082b3b9a7fc195e44291cdcaaa8ec9ba2d9b21ada4f2f3fa249ba"


def test_corpus_hash_is_pinned() -> None:
    digest = hashlib.sha256(_CORPUS.read_bytes()).hexdigest()
    assert digest == CITATION_GRAMMAR_V1_SHA256


def test_parse_citations_matches_shared_corpus() -> None:
    cases = json.loads(_CORPUS.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        scan = parse_citations(case["markdown"])
        got = [{"citekey": c.citekey, "locator": c.locator} for c in scan.citations]
        assert got == case["citations"], case["name"]
        assert sorted(scan.unsupported) == sorted(case["unsupported"]), case["name"]


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


def test_build_reference_bundle_shape(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text(
        "@article{Williams2018,\n  author = {Williams, Donald R.},\n"
        "  title = {Bayesian Meta-Analysis},\n  journal = {PsyArXiv},\n  year = {2018},\n}\n",
        encoding="utf-8",
    )
    bundle = build_reference_bundle(tmp_path)
    assert bundle["contract"] == "science.references"
    assert bundle["schema_version"] == "1"
    assert bundle["style"] == "numeric"
    assert bundle["unresolved"] == {}
    rec = bundle["references"]["Williams2018"]
    assert rec["id"] == "cite:Williams2018"
    assert rec["display"].startswith("Williams DR. Bayesian Meta-Analysis.")


def test_build_reference_bundle_includes_all_entries_not_only_cited(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text(
        "@article{A2020,\n  title = {A},\n  year = {2020},\n}\n\n"
        "@article{B2021,\n  title = {B},\n  year = {2021},\n}\n",
        encoding="utf-8",
    )
    bundle = build_reference_bundle(tmp_path)
    assert set(bundle["references"]) == {"A2020", "B2021"}  # locked decision §16.1


def test_build_reference_bundle_rejects_duplicate_citekeys(tmp_path: Path) -> None:
    (tmp_path / "papers").mkdir()
    (tmp_path / "papers" / "references.bib").write_text(
        "@article{Dup2020,\n  title = {First},\n  year = {2020},\n}\n\n"
        "@article{Dup2020,\n  title = {Second},\n  year = {2021},\n}\n",
        encoding="utf-8",
    )
    with pytest.raises(DuplicateCitekeyError) as exc:
        build_reference_bundle(tmp_path)
    assert exc.value.duplicates == {"Dup2020": 2}


def _payload(text: str) -> list[MarkdownPayload]:
    return [MarkdownPayload(path="findings/leads/x.json", field="sections[0].body", text=text)]


def test_validate_passes_known_keys() -> None:
    assert validate_exported_markdown(_payload("ok [@Smith2020]"), {"Smith2020"}) == {}


def test_validate_fails_closed_on_unknown_key() -> None:
    with pytest.raises(UnresolvedCitationError) as exc:
        validate_exported_markdown(_payload("bad [@Missing2026]"), {"Smith2020"})
    assert "Missing2026" in exc.value.unresolved


def test_validate_visible_placeholder_citekey_still_fails_closed() -> None:
    with pytest.raises(UnresolvedCitationError) as exc:
        validate_exported_markdown(_payload("Visible placeholder [@citekey]."), {"Smith2020"})
    assert "citekey" in exc.value.unresolved


def test_validate_partial_returns_unresolved_block() -> None:
    unresolved = validate_exported_markdown(
        _payload("bad [@Missing2026]"), {"Smith2020"}, allow_partial=True
    )
    entry = unresolved["Missing2026"][0]
    assert entry["citekey"] == "Missing2026"
    assert entry["reason"] == "unknown-citekey"
    assert entry["path"] == "findings/leads/x.json"
    assert entry["field"] == "sections[0].body"
    assert "Missing2026" in entry["snippet"]


def test_validate_fails_on_unsupported_syntax_even_with_partial() -> None:
    with pytest.raises(UnsupportedCitationSyntaxError):
        validate_exported_markdown(_payload("see [-@Smith2020]"), {"Smith2020"}, allow_partial=True)


def _citation_pairs(markdown: str) -> list[tuple[str, str | None]]:
    scan = parse_citations(markdown)
    assert scan.unsupported == []
    return [(citation.citekey, citation.locator) for citation in scan.citations]


def test_parse_citations_ignores_single_line_html_comment() -> None:
    markdown = "<!-- Template citation [@citekey] -->\nVisible [@Smith2020]."
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_ignores_multiline_html_comment() -> None:
    markdown = """Intro.
<!--
Draft note [@Missing2026] and bare @AlsoMissing.
-->
Visible [@Smith2020]."""
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_scans_text_around_same_line_html_comment() -> None:
    markdown = "Before [@Smith2020] <!-- ignored [@citekey] --> after [@Jones2021, p. 42]."
    assert _citation_pairs(markdown) == [("Smith2020", None), ("Jones2021", "p. 42")]


def test_parse_citations_strips_multiple_comments_on_one_line() -> None:
    markdown = "x <!-- ignored [@citekey] --> y <!-- ignored [@Missing2026] --> z [@Smith2020]"
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_preserves_stray_comment_closer() -> None:
    markdown = "A --> B [@Smith2020]."
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_ignores_comment_marker_inside_inline_code() -> None:
    markdown = "Use `<!--` in HTML examples, then cite [@Smith2020]."
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_ignores_comment_marker_inside_multibacktick_inline_code() -> None:
    markdown = "Use ``<!--`` in HTML examples, then cite [@Smith2020]."
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_ignores_comment_marker_inside_multiline_inline_code() -> None:
    markdown = "Use `<!--\nas literal text` and cite [@Smith2020]."
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_ignores_citations_inside_longer_fenced_code() -> None:
    markdown = """````markdown
```
Code cites [@Missing2026].
```
````
Visible [@Smith2020]."""
    assert _citation_pairs(markdown) == [("Smith2020", None)]


def test_parse_citations_treats_comment_closer_inside_comment_as_visible_boundary() -> None:
    markdown = "Before <!-- author `-->` after [@Jones2021] --> visible [@Smith2020]."
    assert _citation_pairs(markdown) == [("Jones2021", None), ("Smith2020", None)]


def test_parse_citations_fails_closed_on_unterminated_html_comment() -> None:
    with pytest.raises(UnterminatedHtmlCommentError, match="unterminated HTML comment"):
        parse_citations("Visible [@Smith2020].\n<!-- author note [@citekey]\nVisible [@Jones2021].")

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from science_tool.bibliography import BibEntry
from science_tool.references import CONTRACT, SCHEMA_VERSION, format_authors, format_display, reference_record, parse_citations

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

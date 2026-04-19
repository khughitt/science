from __future__ import annotations

from science_tool.big_picture.literature_prefix import (
    canonical_paper_id,
    is_external_paper_id,
)


def test_canonicalizes_article_prefix() -> None:
    assert canonical_paper_id("article:Smith2024") == "paper:Smith2024"


def test_passes_through_paper_prefix() -> None:
    assert canonical_paper_id("paper:Smith2024") == "paper:Smith2024"


def test_passes_through_other_prefixes_unchanged() -> None:
    assert canonical_paper_id("question:q01") == "question:q01"
    assert canonical_paper_id("cite:Smith2024") == "cite:Smith2024"
    assert canonical_paper_id("manuscript:m01") == "manuscript:m01"


def test_is_external_paper_id_accepts_both() -> None:
    assert is_external_paper_id("paper:Smith2024")
    assert is_external_paper_id("article:Smith2024")
    assert not is_external_paper_id("cite:Smith2024")
    assert not is_external_paper_id("topic:ribosome")

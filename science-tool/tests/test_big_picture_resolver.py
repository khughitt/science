from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.resolver import resolve_questions

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_direct_match() -> None:
    result = resolve_questions(FIXTURE)
    q01 = result["question:q01-direct-to-h1"]
    assert q01.primary_hypothesis == "hypothesis:h1-alpha"
    assert any(m.id == "hypothesis:h1-alpha" and m.confidence == "direct" for m in q01.hypotheses)

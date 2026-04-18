from __future__ import annotations

from pathlib import Path

from science_tool.big_picture.resolver import resolve_questions

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_direct_match() -> None:
    result = resolve_questions(FIXTURE)
    q01 = result["question:q01-direct-to-h1"]
    assert q01.primary_hypothesis == "hypothesis:h1-alpha"
    assert any(m.id == "hypothesis:h1-alpha" and m.confidence == "direct" for m in q01.hypotheses)


def test_inverse_match() -> None:
    result = resolve_questions(FIXTURE)
    q02 = result["question:q02-inverse-via-h1"]
    assert q02.primary_hypothesis == "hypothesis:h1-alpha"
    match = next(m for m in q02.hypotheses if m.id == "hypothesis:h1-alpha")
    assert match.confidence == "inverse"


def test_transitive_match() -> None:
    result = resolve_questions(FIXTURE)
    q03 = result["question:q03-transitive-via-interp"]
    assert q03.primary_hypothesis == "hypothesis:h1-alpha"
    match = next(m for m in q03.hypotheses if m.id == "hypothesis:h1-alpha")
    assert match.confidence == "transitive"


def test_cross_cutting_many_to_many() -> None:
    result = resolve_questions(FIXTURE)
    q04 = result["question:q04-cross-cutting"]
    hyp_ids = {m.id for m in q04.hypotheses}
    assert hyp_ids == {"hypothesis:h1-alpha", "hypothesis:h2-beta"}
    # Both are inverse-matched (both hypotheses list q04 in related).
    assert all(m.confidence == "inverse" for m in q04.hypotheses)


def test_orphan_has_null_primary() -> None:
    result = resolve_questions(FIXTURE)
    q05 = result["question:q05-orphan"]
    assert q05.primary_hypothesis is None
    assert q05.hypotheses == []


def test_primary_prefers_higher_confidence() -> None:
    """A question matched both inverse and transitive prefers the inverse match."""
    result = resolve_questions(FIXTURE)
    q02 = result["question:q02-inverse-via-h1"]
    assert q02.primary_hypothesis == "hypothesis:h1-alpha"
    assert q02.hypotheses[0].confidence == "inverse"

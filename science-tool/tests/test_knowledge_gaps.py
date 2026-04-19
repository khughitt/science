from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.big_picture.knowledge_gaps import (
    TopicGap,
    _compute_demand,
    _load_papers,
    _load_topics,
)
from science_tool.big_picture.resolver import resolve_questions

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_topic_gap_is_frozen_dataclass() -> None:
    tg = TopicGap(
        topic_id="topic:foo",
        coverage=1,
        demand=3,
        gap_score=2,
        demanding_questions=["question:q01"],
        hypotheses=["h1"],
    )
    assert tg.topic_id == "topic:foo"
    assert tg.gap_score == 2
    # Frozen: mutation raises.
    import dataclasses as dc
    assert dc.is_dataclass(tg) and tg.__dataclass_params__.frozen  # type: ignore[attr-defined]


def test_load_topics_finds_all_fixture_topics() -> None:
    topics = _load_topics(FIXTURE)
    assert set(topics) == {
        "topic:t01-covered",
        "topic:t02-thin",
        "topic:t03-bibtex-covered",
        "topic:t04-legacy-covered",
    }


def test_load_papers_finds_both_prefix_styles() -> None:
    papers = _load_papers(FIXTURE)
    # Legacy `article:` entity canonicalizes to `paper:` in the returned keys.
    assert "paper:p01-example" in papers
    assert "paper:p02-legacy-article" in papers


def test_duplicate_topic_ids_across_topic_directories_raise(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Place a duplicate topic in doc/topics/ (second scanned root).
    (project / "doc" / "topics").mkdir(parents=True)
    (project / "doc" / "topics" / "t01-covered.md").write_text(
        '---\nid: "topic:t01-covered"\ntype: "topic"\nrelated: []\n---\n'
    )
    with pytest.raises(ValueError, match="t01-covered"):
        _load_topics(project)


def test_duplicate_paper_ids_across_paper_directories_raise(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    (project / "doc" / "background" / "papers").mkdir(parents=True)
    (project / "doc" / "background" / "papers" / "p01-example.md").write_text(
        '---\nid: "paper:p01-example"\ntype: "paper"\nrelated: []\n---\n'
    )
    with pytest.raises(ValueError, match="p01-example"):
        _load_papers(project)


# Task 4: Coverage computation tests


def test_coverage_via_entity_linked_paper() -> None:
    from science_tool.big_picture.knowledge_gaps import _compute_coverage

    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    cov = _compute_coverage("topic:t01-covered", topics, papers)
    assert cov == 1


def test_coverage_zero_for_uncovered_topic() -> None:
    from science_tool.big_picture.knowledge_gaps import _compute_coverage

    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    assert _compute_coverage("topic:t02-thin", topics, papers) == 0


def test_coverage_via_bibtex_source_refs() -> None:
    from science_tool.big_picture.knowledge_gaps import _compute_coverage

    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    assert _compute_coverage("topic:t03-bibtex-covered", topics, papers) == 1


def test_coverage_accepts_article_prefix_paper_as_legacy_alias() -> None:
    from science_tool.big_picture.knowledge_gaps import _compute_coverage

    topics = _load_topics(FIXTURE)
    papers = _load_papers(FIXTURE)
    # p02 has id: article:... which canonicalizes to paper:p02-legacy-article
    # and lists topic:t04 as a relation.
    assert _compute_coverage("topic:t04-legacy-covered", topics, papers) == 1


def test_coverage_dedupes_bibkey_across_entity_and_source_refs(tmp_path: Path) -> None:
    from science_tool.big_picture.knowledge_gaps import _compute_coverage

    # Same bibkey reached via both paper entity AND topic's source_refs:
    # should count as 1, not 2.
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Edit t01 to also source_refs the same bibkey as its entity-linked paper.
    t01 = project / "doc" / "background" / "topics" / "t01-covered.md"
    text = t01.read_text()
    text = text.replace(
        "source_refs: []",
        "source_refs: [cite:p01-example]",
    )
    t01.write_text(text)

    topics = _load_topics(project)
    papers = _load_papers(project)
    assert _compute_coverage("topic:t01-covered", topics, papers) == 1


# Task 5: Demand computation tests


def test_demand_counts_direct_references() -> None:
    resolved = resolve_questions(FIXTURE)
    included = set(resolved.keys())
    # q01 references t02-thin (per fixture task); q02 also references it.
    demand, demanders = _compute_demand(FIXTURE, "topic:t02-thin", included)
    assert demand == 2
    assert set(demanders) == {"question:q01-direct-to-h1", "question:q02-inverse-via-h1"}


def test_demand_respects_included_question_ids_filter() -> None:
    resolved = resolve_questions(FIXTURE)
    # Exclude q02 via the filter argument; demand for t02 drops to 1.
    included = {qid for qid in resolved if qid != "question:q02-inverse-via-h1"}
    demand, demanders = _compute_demand(FIXTURE, "topic:t02-thin", included)
    assert demand == 1
    assert demanders == ["question:q01-direct-to-h1"]


def test_demand_zero_for_unreferenced_topic(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "p")
    project = tmp_path / "p"
    # Add an orphan topic nobody references.
    (project / "doc" / "background" / "topics" / "t99-orphan.md").write_text(
        '---\nid: "topic:t99-orphan"\ntype: "topic"\nrelated: []\n---\n'
    )
    resolved = resolve_questions(project)
    demand, demanders = _compute_demand(project, "topic:t99-orphan", set(resolved))
    assert demand == 0
    assert demanders == []

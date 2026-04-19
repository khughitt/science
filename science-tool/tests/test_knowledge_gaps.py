from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.big_picture.knowledge_gaps import TopicGap, _load_papers, _load_topics

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

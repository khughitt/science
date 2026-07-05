"""Knowledge-gaps loaders honor default visibility (consolidation P1)."""

from __future__ import annotations

from pathlib import Path


def test_superseded_topic_is_excluded_from_topic_load(tmp_path: Path) -> None:
    (tmp_path / "entities" / "topics").mkdir(parents=True)
    (tmp_path / "science.yaml").write_text("name: kg\n")
    (tmp_path / "entities" / "topics" / "t01.md").write_text(
        '---\nid: "topic:t01"\nkind: "topic"\nstatus: "active"\n---\nlive.\n'
    )
    (tmp_path / "entities" / "topics" / "t02.md").write_text(
        '---\nid: "topic:t02"\nkind: "topic"\nstatus: "superseded"\n---\nold.\n'
    )

    from science_tool.big_picture.knowledge_gaps import _load_topics

    topics = _load_topics(tmp_path)
    assert "topic:t01" in topics
    assert "topic:t02" not in topics

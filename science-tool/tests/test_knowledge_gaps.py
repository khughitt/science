from __future__ import annotations

from science_tool.big_picture.knowledge_gaps import TopicGap


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

import pytest

from science_tool.drift_sample.draw import draw
from science_tool.drift_sample.frame import FrameRow


def _frame(size: int) -> list[FrameRow]:
    return [
        FrameRow(f"plan:{i:04d}-x", "proj", f"entities/plans/{i:04d}-x.md", "draft", "0" * 64)
        for i in range(size)
    ]


def test_draw_is_deterministic_given_a_seed():
    frame = _frame(100)
    assert [r.plan_id for r in draw(frame, 10, seed=42)] == [
        r.plan_id for r in draw(frame, 10, seed=42)
    ]


def test_different_seeds_give_different_draws():
    frame = _frame(100)
    assert [r.plan_id for r in draw(frame, 10, seed=1)] != [
        r.plan_id for r in draw(frame, 10, seed=2)
    ]


def test_draw_is_without_replacement():
    ids = [r.plan_id for r in draw(_frame(100), 40, seed=7)]
    assert len(ids) == len(set(ids)) == 40


def test_draw_is_independent_of_frame_order():
    """Selection must not depend on how the frame happened to be enumerated."""
    frame = _frame(100)
    shuffled = list(reversed(frame))
    assert sorted(r.plan_id for r in draw(frame, 10, seed=3)) == sorted(
        r.plan_id for r in draw(shuffled, 10, seed=3)
    )


def test_draw_larger_than_frame_is_a_census():
    assert len(draw(_frame(10), 40, seed=1)) == 10


def test_draw_rejects_a_duplicate_frame():
    dup = _frame(3) + _frame(3)
    with pytest.raises(ValueError, match="duplicate"):
        draw(dup, 2, seed=1)
